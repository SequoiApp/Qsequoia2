from pathlib import Path
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import QgsProject, QgsApplication
from PyQt5.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QTreeWidgetItem
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt

from ..utils.seq_config import seq_layer
from .ua_checker_utils import *

UI_PATH = Path(__file__).parent / 'ua_checker.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class ua_checker(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.setupUi(self)

        self.btn_refresh.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.btn_refresh.clicked.connect(self.on_ua_layer_loaded)

        self._setup_ui_errors(False)

        self.cb_pf.currentTextChanged.connect(lambda value: self._on_cb_pf_changed(value))
        self.cb_sspf.currentTextChanged.connect(lambda value: self._on_cb_pf_changed(value))
        self.project.layersRemoved.connect(self._on_layers_removed)

    def _find_ua_loader(self):
        meta = seq_layer("ua")
        for layer in self.project.mapLayers().values():
            source = layer.source()
            if not source or "://" in source:
                continue
                
            path = Path(source)
            if meta["filename"] in path.name :
                return layer
        return None

    def on_ua_layer_loaded(self): 
        self.ua_layer = self._find_ua_loader()

        if not self.ua_layer:
            self._ua_status(state=False)
            self._ui_status(state = False)
            return

        self._ua_status(state=True)
        self._ui_status(state = True)
        self._check_data()
        self.populate_cb_from_field("cb_pf", self.ua_layer, "N_PARFOR")
        self.populate_cb_from_field("cb_sspf", self.ua_layer, "N_SSPARFOR")

    def _ua_status(self, state):
        if state:
            self.lbl_ua_status.setText("Couche UA chargée")
            self.lbl_ua_status.setStyleSheet("color: green;")
        else:
            self.lbl_ua_status.setText("Couche UA non chargée")
            self.lbl_ua_status.setStyleSheet("color: red;")

    def _check_data(self):
        inconsistent_ug = ua_check_ug(self.ua_layer)
        self._set_checker_status(inconsistent_ug)
        self.ua_layer.removeSelection()
        self.lbl_surf_sig.setText(f"Surface SIG : {sspf_surface_calculation(self.ua_layer)}")
        self.lbl_nb_pf.setText(f"Nombre parcelles forestières : {str(len(get_pf_list(self.ua_layer)))}")
        self.lbl_nb_sspf.setText(f"Nombre sous-parcelles forestières : {str(len(get_sspf_list(self.ua_layer)))}")

    # Utilitaire pour UI 
    def _ui_status(self, state):
        self.cb_pf.setEnabled(state)
        self.cb_sspf.setEnabled(state)
    
    def _setup_ui_errors(self, state):
        self.lbl_errors.setVisible(state)
        self.tree_checker.setVisible(state)
    
    def _on_layers_removed(self):
        QTimer.singleShot(0,self.on_ua_layer_loaded)

    def populate_cb_from_field(self, cb_name, layer, field_name):

        cb = getattr(self, cb_name)
        values = sorted({str(f[field_name]) for f in layer.getFeatures()})
        cb.clear()
        cb.addItem("")
        cb.addItems(values)
        cb.setCurrentIndex(0)

    def _on_cb_pf_changed(self, value=None, pf_value=None, sspf_value=None):

        if value is not None:
            pf_value = self.cb_pf.currentText()
            sspf_value = self.cb_sspf.currentText()

        expr = self.build_sspf_expression(pf_value, sspf_value)
        
        if expr is None:
            self.ua_layer.removeSelection()

        ids = select_feats_by_expression(self.ua_layer, expr, self.iface)

        if ids:
            surf = sspf_surface_calculation(self.ua_layer)
            if surf:
                self.lbl_surf_sig.setText(f"Surface SIG : {surf}")

    def build_sspf_expression(self, pf_value=None, sspf_value=None):

        pf_field = seq_field("pcl_code")["name"]
        sspf_field = seq_field("sub_code")["name"]

        filters = []

        if pf_value == "NULL":
            filters.append(f"\"{pf_field}\" IS NULL")

        elif pf_value not in (None, ""):
            filters.append(f"\"{pf_field}\" = '{pf_value}'")

        if sspf_value == "NULL":
            filters.append(f"\"{sspf_field}\" IS NULL")

        elif sspf_value not in (None, ""):
            filters.append(f"\"{sspf_field}\" = '{sspf_value}'")

        if not filters:
            return None

        return " AND ".join(filters)


    def _set_checker_status(self, inc_ua=None):

        if not inc_ua:
            self._setup_ui_errors(False)
            return

        self._setup_ui_errors(True)
        self._fill_checker_tree(inc_ua)


    def _fill_checker_tree(self, bad_ua):

        tree = self.tree_checker
        tree.itemDoubleClicked.connect(self._on_tree_item_clicked)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIndentation(0)
        tree.clear()

        icon = QgsApplication.getThemeIcon("/mIconWarning.svg")

        for n_parfor, fields in bad_ua.items():

            for field, values in fields.items():

                vals = ", ".join(str(v) for v in values)

                warn = ""

                item = QTreeWidgetItem([warn, n_parfor, field, vals])
                item.setIcon(0, icon)

                for col in range(4):
                    item.setBackground(col, QColor(255, 220, 220))
                    item.setForeground(col, QColor(120, 0, 0))
                    item.setTextAlignment(col, Qt.AlignCenter)

                tree.addTopLevelItem(item)
                
        for col in range(4):
            tree.resizeColumnToContents(col)

    def _on_tree_item_clicked(self,item):
        n_parfor = item.text(1)
        pf = n_parfor.split(".")[0]
        sspf = n_parfor.split(".")[1]
        self._on_cb_pf_changed(value=None,pf_value=pf,sspf_value=sspf)




        