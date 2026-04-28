from pathlib import Path

from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import QgsProject, QgsApplication, QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsFeatureRequest
from PyQt5.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QTreeWidgetItem
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import Qt


from ..utils.seq_config import seq_layer
from ..utils.Qmessage import messageLog
from .data_table import *

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


        # réaction au changement de parcelle sélectionnée, lambda pour éviter de devoir passer la valeur à la fonction
        self.cb_parcelle.currentTextChanged.connect(lambda value: self._on_cb_parcelle_changed(value))
        self.cb_sspf.currentTextChanged.connect(lambda value: self._on_cb_parcelle_changed(value))
        QgsProject.instance().layersRemoved.connect(self._on_layers_removed)

    def on_project_loaded(self):
        # attendre que QGIS ait fini de charger les couches et le projet
        QTimer.singleShot(300, self.on_ua_layer_loaded)


    def on_ua_layer_loaded(self): 

        layer = self._ua_loader()

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


    def _ua_loader(self):

        project = QgsProject.instance()
        meta = seq_layer("ua")

        for layer in project.mapLayers().values():
            source = layer.source()
            if not source or "://" in source:
                continue
                
            path = Path(source)
            if meta["filename"] in path.name :
                return layer
            
        return None
                  

    def _ua_status(self, state):
        if state:
            self.lbl_ua_status.setText("Couche UA chargée")
            self.lbl_ua_status.setStyleSheet("color: green;")
        else:
            self.lbl_ua_status.setText("Couche UA non chargée")
            self.lbl_ua_status.setStyleSheet("color: red;")

    def _check_data(self, ids=None):

        if ids is not None:
            ua_feats = [f for f in self.ua_layer.getFeatures() if f.id() in ids]
            bad_fields, good_fields = self.check_feats(self.ua_layer)
            self._set_checker_status(bad_fields)
        else:
            ua_feats = list(self.ua_layer.getFeatures())
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
    

    def _on_layers_removed(self, layer_ids):
        QTimer.singleShot(0,self.on_ua_layer_loaded)

    # Utilitaire pour remplir les comboBox de sélection

    def populate_cb_from_field(self, cb_name, layer, field_name):

        cb = getattr(self, cb_name)
        values = sorted({str(f[field_name]) for f in layer.getFeatures()})
        cb.clear()
        # cb.addItem("Toutes")      # valeur par défaut
        cb.addItems(values)
        cb.setCurrentIndex(0)


    def _on_cb_parcelle_changed(self, value):

        expr = self.build_sspf_expression(self.ua_layer, value)

        if expr:
            ids = self.selectFeaturesByExpression(self.ua_layer, expr)

            if ids is not None:
                self._check_data(ids=ids)
                surf = sspf_surface_calculation(self.ua_layer)
                if surf:
                    self.le_surf.setText(surf)

        else:
            self._check_data()


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


    def check_feats(self, ua_layer):
        index_list = get_seq_config("seq_tables")["ua"]

        index_to_skip = [
            "idu", "reg_name", "reg_code", "dep_name", "dep_code",
            "com_name", "com_code", "insee", "prefix", "section",
            "number", "locality", "gis_area", "cor_area", "cad_area"
        ]

        index_list = [k.strip() for k in index_list if k.strip() not in index_to_skip]
        results = {}

        for index in index_list:

            field = seq_field(index)["name"]

            if not ua_layer.selectedFeatures():
                return {},{}
            
            feats_list = get_feats(ua_layer, field)
            
            checked, formatted = check_values(feats_list)
            pf = get_pf_list(ua_layer, True)
            sspf = get_sspf_list(ua_layer, pf, True)
            n_parfor = pf[0] + "." + sspf[0]
            
            results[index] = {
                "n_parfor" : n_parfor,
                "checked": checked,
                "values": formatted
                }
            bad_fields = {k: v for k, v in results.items() if v["checked"] is False}
            good_fields = {k: v for k, v in results.items() if v["checked"] is True}

        return bad_fields, good_fields
    
    def _set_checker_status(self, bad_fields= None):

        if bad_fields:
            first_field = next(iter(bad_fields))
            n_parfor = bad_fields[first_field]["n_parfor"]
            messageLog(f"[UA_CHECKER] : Plusieurs {list(bad_fields.keys())} pour la sous-parcelle {n_parfor}")
            
            self._setup_ui_errors(True)
            self.lbl_feats_status.setPixmap(QgsApplication.getThemeIcon("/mIconWarning.svg").pixmap(16, 16))
            self.fill_checker_tree(bad_fields)

        else : 
            self._setup_ui_errors(False)            
            self.lbl_feats_status.setPixmap(QgsApplication.getThemeIcon("/mIconSuccess.svg").pixmap(16, 16))


    def fill_checker_tree(self, bad_fields):
        
        tree = self.tree_checker
        tree.itemDoubleClicked.connect(self._open_attribute_table)
        tree.setHeaderHidden(True)
        tree.setRootIsDecorated(False)
        tree.setIndentation(0)
        tree.clear()

        icon = QgsApplication.getThemeIcon("/mIconWarning.svg")

        for field, info in bad_fields.items():
            vals = ", ".join(str(v) for v in info["values"])
            warn = ""
            item = QTreeWidgetItem([warn, field, vals])
            item.setIcon(0, icon)

            for col in range(3):
                item.setBackground(col, QColor(255, 220, 220))
                item.setForeground(col, QColor(120, 0, 0))
                item.setTextAlignment(col, Qt.AlignCenter)

            tree.addTopLevelItem(item)

        tree.resizeColumnToContents(0)
        tree.resizeColumnToContents(1)
        tree.resizeColumnToContents(2)


    def _open_attribute_table(self):
        self.iface.showAttributeTable(self.ua_layer)


        