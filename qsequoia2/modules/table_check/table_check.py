from pathlib import Path

from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import *
from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt, QTimer

from ..utils.seq_config import seq_layer

UI_PATH = Path(__file__).parent / 'table_check.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class table_check(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.setupUi(self)

        self.forestTable.setVisible(False)

        self.btn_refresh.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.btn_refresh.clicked.connect(self.on_ua_layer_loaded)


        # réaction au changement de parcelle sélectionnée, lambda pour éviter de devoir passer la valeur à la fonction
        self.cb_parcelle.currentTextChanged.connect(lambda value: self._on_cb_parcelle_changed(value))
        self.cb_sspf.currentTextChanged.connect(lambda value: self._on_cb_parcelle_changed(value))
        QgsProject.instance().layersRemoved.connect(self._on_layers_removed)

    def on_project_loaded(self):
        # attendre que QGIS ait fini de charger les couches et le projet
        QTimer.singleShot(300, self.on_ua_layer_loaded)

    def on_ua_layer_loaded(self):
        layer_name = seq_layer("ua")["name"]

        layer = None
        for l in QgsProject.instance().mapLayers().values():
            if l.name() == layer_name:
                layer = l
                break

        if not layer:
            self._ua_status(state=False)
            self._setup_ui_verif(state = False)
            return

        self.ua_layer = layer
        self._ua_status(state=True)
        self._setup_ui_verif(state = True)
        self._check_data()
        self.populate_cb_from_field("cb_parcelle", layer, "N_PARFOR")
        self.populate_cb_from_field("cb_sspf", layer, "N_SSPARFOR")

    def _ua_status(self, state):
        if state:
            self.lbl_ua_status.setText("Couche UA chargée")
            self.lbl_ua_status.setStyleSheet("color: green;")
        else:
            self.lbl_ua_status.setText("Couche UA non chargée")
            self.lbl_ua_status.setStyleSheet("color: red;")

    def _check_data(self, ids=None):

        self.forestTable.clearContents()
        self.forestTable.setRowCount(0)

        if ids is not None:
            ua_feats = [f for f in self.ua_layer.getFeatures() if f.id() in ids]
        else:
            ua_feats = list(self.ua_layer.getFeatures())
            self.ua_layer.removeSelection()
            surf = self.sspf_surface_calculation(self.ua_layer)
            self.le_surf.setText(surf)

        self.fill_table(self.ua_layer, ua_feats)

    # Utilitaire pour UI 
    def _setup_ui_verif(self, state):
        self.forestTable.setVisible(state)

        self.forestTable.clearContents()
        self.forestTable.setRowCount(0)

        self.cb_parcelle.setEnabled(state)
        self.cb_sspf.setEnabled(state)
        self.cb_sspf.setEnabled(state)
        self.lbl_sspf.setEnabled(state)
        self.lbl_surf.setEnabled(state)
        self.le_surf.setEnabled(state)
    

    def _on_layers_removed(self, layer_ids):
        QTimer.singleShot(0,self.on_ua_layer_loaded)

    # Utilitaire pour remplir les comboBox de sélection

    def populate_cb_from_field(self, cb_name, layer, field_name):

        cb = getattr(self, cb_name)
        values = sorted({str(f[field_name]) for f in layer.getFeatures()})
        cb.clear()
        cb.addItem("Toutes")      # valeur par défaut
        cb.addItems(values)
        cb.setCurrentIndex(0)


    def _on_cb_parcelle_changed(self, value):

        expr = self.build_sspf_expression(self.ua_layer, value)

        if expr:
            ids = self.selectFeaturesByExpression(self.ua_layer, expr)

            if ids is not None:
                self._check_data(ids=ids)
                surf = self.sspf_surface_calculation(self.ua_layer)
                if surf:
                    self.le_surf.setText(surf)

        else:
            self._check_data()


    def fill_table(self, ua_layer, ua_feats):
        """Remplit la table avec les features données"""

        fields = ua_layer.fields()

        self.forestTable.setColumnCount(len(fields))
        self.forestTable.setHorizontalHeaderLabels([f.name() for f in fields])
        self.forestTable.setRowCount(len(ua_feats))

        # met en forme la table
        self.Table_format()

        for row, feat in enumerate(ua_feats):
            for col, field in enumerate(fields):
                val = feat[field.name()]
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.forestTable.setItem(row, col, item)

    def Table_format(self):
        """Met en forme la table"""
        header = self.forestTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.forestTable.setAlternatingRowColors(True)


    def build_sspf_expression(self, layer,value):

        # Construction dynamique des filtres
        filters = []
        pf_value = self.cb_parcelle.currentText()
        sspf_value = self.cb_sspf.currentText()

        if value != "Toutes":
            filters.append(f"\"N_PARFOR\" = '{pf_value}'")

        if "N_SSPARFOR" in [field.name() for field in layer.fields()]:
            if sspf_value != "Toutes":
                filters.append(f"\"N_SSPARFOR\" = '{sspf_value}'")

        # Si aucun filtre → tout afficher
        if not filters:
            return None 

        expr = " AND ".join(filters)
        return expr
    
    
    def selectFeaturesByExpression(self, layer, expr):
        """"""

        exp = QgsExpression(expr)
        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
        request = QgsFeatureRequest(exp, context)

        ids = [f.id() for f in layer.getFeatures(request)]

        self.iface.layerTreeView().setCurrentLayer(layer)

        layer.removeSelection()
        layer.selectByIds(ids)

        self.iface.mapCanvas().zoomToSelected(layer)
        self.iface.mapCanvas().refresh()

        return ids
        
    def sspf_surface_calculation(self,ua_layer) -> str:

        feats = list(ua_layer.getSelectedFeatures())
        if not feats: 
            surf = sum(f.geometry().area() for f in ua_layer.getFeatures()) / 10000
            return f"{round(surf,4)} ha"
        tmp = QgsVectorLayer("Polygon?crs=" + ua_layer.crs().authid(), "tmp", "memory")
        tmp.dataProvider().addFeatures(feats)
        surf = sum(f.geometry().area() for f in tmp.getFeatures()) / 10000
        return f"{round(surf,4)} ha"