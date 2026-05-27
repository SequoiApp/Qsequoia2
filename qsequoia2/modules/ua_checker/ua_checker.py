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

        self.cb_parcelle.currentTextChanged.connect(lambda value: self._on_cb_parcelle_changed(value))
        self.cb_sspf.currentTextChanged.connect(lambda value: self._on_cb_parcelle_changed(value))
        self.project.layersRemoved.connect(self._on_layers_removed)

    def on_project_loaded(self):
        # attendre que QGIS ait fini de charger les couches et le projet
        QTimer.singleShot(300, self.on_ua_layer_loaded)


    def _ua_loader(self):
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
        self.ua_layer = self._ua_loader()

        if not self.ua_layer:
            self._ua_status(state=False)
            self._setup_ui_verif(state = False)
            return

        self._ua_status(state=True)
        self._setup_ui_verif(state = True)
        self._check_data()
        self.populate_cb_from_field("cb_parcelle", self.ua_layer, "N_PARFOR")
        self.populate_cb_from_field("cb_sspf", self.ua_layer, "N_SSPARFOR")

    def _ua_status(self, state):
        if state:
            self.lbl_ua_status.setText("Couche UA chargée")
            self.lbl_ua_status.setStyleSheet("color: green;")
        else:
            self.lbl_ua_status.setText("Couche UA non chargée")
            self.lbl_ua_status.setStyleSheet("color: red;")

    def _check_data(self):

        inc_ua = ua_check_ug(self.ua_layer)
        self._set_checker_status(inc_ua)
        self.ua_layer.removeSelection()

        for_ui = {
                    "pf_list" : get_pf_list(self.ua_layer),
                    "sspf_list" : get_sspf_list(self.ua_layer),
                    "surf" : sspf_surface_calculation(self.ua_layer)
                }

        self.add_in_ui(for_ui)

    def add_in_ui(self, ui):
        self.le_surf.setText(ui["surf"])
        self.le_nb_pf.setText(str(len(ui["pf_list"])))
        self.le_nb_sspf.setText(str(len(ui["sspf_list"])))

    # Utilitaire pour UI 
    def _setup_ui_verif(self, state):

        self.cb_parcelle.setEnabled(state)
        self.cb_sspf.setEnabled(state)
        self.cb_sspf.setEnabled(state)
        self.lbl_sspf.setEnabled(state)
        self.lbl_surf.setEnabled(state)
        self.le_surf.setEnabled(state)
    
    def _setup_ui_errors(self, state):
        self.lbl_errors.setVisible(state)
        self.lbl_feats_status.setVisible(state)
        self.tree_checker.setVisible(state)
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

    def _on_cb_parcelle_changed(self, value=None, pf_value=None, sspf_value=None):

        if value is not None:
            pf_value = self.cb_parcelle.currentText()
            sspf_value = self.cb_sspf.currentText()

        expr = self.build_sspf_expression(pf_value, sspf_value)
        
        if expr is None:
            self.ua_layer.removeSelection()
        if expr:
            ids = selectFeaturesByExpression(self.ua_layer, expr, self.iface)

            if ids:
                surf = sspf_surface_calculation(self.ua_layer)
                if surf:
                    self.le_surf.setText(surf)

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
            self.lbl_feats_status.setPixmap(QgsApplication.getThemeIcon("/mIconSuccess.svg").pixmap(16, 16))
            return

        self._setup_ui_errors(True)
        self.lbl_feats_status.setPixmap(QgsApplication.getThemeIcon("/mIconWarning.svg").pixmap(16, 16))
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
        self._on_cb_parcelle_changed(value=None,pf_value=pf,sspf_value=sspf)




        