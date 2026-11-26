from pathlib import Path

from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QWidget, QTreeWidgetItem
from qgis.core import QgsProject, QgsApplication

from qsequoia2.modules.utils.Qmessage import messageBar, messageBox
from qsequoia2.modules.utils.seq_config import resolve_seq_layer, seq_field
from qsequoia2.modules.utils.variable import get_project_variable

from .ua_checker_utils import (
    get_pf_list,
    get_sspf_list,
    select_feats_by_expression,
    sspf_surface_calculation,
    ua_check_ug,
)

UI_PATH = Path(__file__).parent / 'ua_checker.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class UaCheckerWidget(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.project = QgsProject.instance()
        self.ua_layer = None
        self.setupUi(self)

        self.pb_ua_status.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.pb_ua_status.clicked.connect(self._on_pb_ua_status_clicked)
        self.pb_check_ug.clicked.connect(self._on_pb_check_ug_clicked)

        self.tree_checker.itemDoubleClicked.connect(self._on_tree_item_clicked)
        self.cb_pf.activated.connect(self._on_filter_changed)
        self.cb_sspf.activated.connect(self._on_filter_changed)

        self._clear_widget()

    def _on_pb_ua_status_clicked(self):
        self._clear_widget()
        seq_id = get_project_variable("QS2_seq_id")
        self.ua_layer = resolve_seq_layer("ua", self.project, seq_id=seq_id)

        if self.ua_layer is None:
            return False

        self.lbl_ua_status.setText("Couche UA chargée")
        self.lbl_ua_status.setStyleSheet("color: green;")
        self._fill_widget()
        return True

    def _on_pb_check_ug_clicked(self):
        if not self._on_pb_ua_status_clicked():
            return

        if not self.ua_layer.isEditable():
            messageBox(
                self.iface,
                "Couche UA non éditable",
                "Activez le mode édition de la couche UA avant de poursuivre.",
                "w"
            )
            return

        report = ua_check_ug(self.ua_layer, auto_fill=self.cb_auto_fill.isChecked())
        self._fill_checker_tree(report)
        self.ua_layer.removeSelection()

        self._fill_widget()
        if not report:
            messageBar(self.iface, "Toutes les UG sont cohérentes.", "s")

    def _clear_widget(self):
        self.ua_layer = None
        self._fill_combo(self.cb_pf, [])
        self._fill_combo(self.cb_sspf, [])
        self._fill_checker_tree({})
        self.lbl_ua_status.setText("Couche UA non chargée")
        self.lbl_ua_status.setStyleSheet("color: red;")
        self.lbl_nb_pf_res.setText("0")
        self.lbl_nb_sspf_res.setText("0")
        self.lbl_surf_sig_res.setText("0 ha")

    def _fill_widget(self):
        pf_values = get_pf_list(self.ua_layer)
        sspf_values = get_sspf_list(self.ua_layer)

        self._fill_combo(self.cb_pf, pf_values)
        self._fill_combo(self.cb_sspf, sspf_values)
        self.lbl_nb_pf_res.setText(str(len(pf_values)))
        self.lbl_nb_sspf_res.setText(str(len(sspf_values)))
        self.lbl_surf_sig_res.setText(sspf_surface_calculation(self.ua_layer))

    def _fill_combo(self, combo, values):
        combo.clear()
        combo.addItem("")
        combo.addItems(sorted({str(value) for value in values}))

    def _on_filter_changed(self):
        if not self.ua_layer:
            return

        pf_value = self.cb_pf.currentText()
        if self.sender() is self.cb_pf:
            self._fill_combo(self.cb_sspf, get_sspf_list(self.ua_layer, pf_list=pf_value or None))

        self._select_features(pf_value, self.cb_sspf.currentText())

    def _select_features(self, pf_value, sspf_value):
        if not self.ua_layer:
            return

        expr = self.build_sspf_expression(pf_value, sspf_value)
        if expr is None:
            self.ua_layer.removeSelection()
        else:
            select_feats_by_expression(self.ua_layer, expr, self.iface)
        self.lbl_surf_sig_res.setText(sspf_surface_calculation(self.ua_layer))

    def build_sspf_expression(self, pf_value=None, sspf_value=None):
        filters = []
        for key, value in (("pcl_code", pf_value), ("sub_code", sspf_value)):
            field = seq_field(key)["name"]
            if value == "NULL":
                filters.append(f'"{field}" IS NULL')
            elif value not in (None, ""):
                value = value.replace("'", "''")
                filters.append(f'"{field}" = \'{value}\'')
        return " AND ".join(filters) or None

    def _fill_checker_tree(self, bad_ua):
        tree = self.tree_checker
        tree.clear()
        tree.setVisible(bool(bad_ua))
        self.lbl_errors.setVisible(bool(bad_ua))
        icon = QgsApplication.getThemeIcon("/mIconWarning.svg")

        for n_parfor, fields in bad_ua.items():
            for field, values in fields.items():
                item = QTreeWidgetItem(["", n_parfor, field, ", ".join(map(str, values))])
                item.setIcon(0, icon)
                for col in range(4):
                    item.setBackground(col, QColor(255, 220, 220))
                    item.setForeground(col, QColor(120, 0, 0))
                    item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

                tree.addTopLevelItem(item)

        for col in range(4):
            tree.resizeColumnToContents(col)

    def _on_tree_item_clicked(self, item):
        pf, sspf = item.text(1).split(".", 1)
        self._select_features(pf, sspf)
