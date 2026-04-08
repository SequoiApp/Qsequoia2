
# ==========================================================================
# import
# ==========================================================================

# python 

from pathlib import Path

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import *
from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt

# Qsequoia2 
from ..utils.Qmessage import *
from .data_table import *
from ..utils.variable import *
from ..utils.seq_config import *

UI_PATH = Path(__file__).parent / 'table_check.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

# ==========================================================================
# region initalisation
# ==========================================================================


class table_check(QDialog, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.setupUi(self)


        self.forestTable.setHidden(True)


        # réaction au changement de type de données à afficher
        self.cb_dataType.currentTextChanged.connect(self.actu_Tabledata)
        # réaction au changement de parcelle sélectionnée
        self.cb_parcelle.currentTextChanged.connect(self.on_cb_parcelle_changed)
        self.cb_sspf.currentTextChanged.connect(self.on_cb_parcelle_changed)

    # endregion
    # ================================================
    # region tableaux
    # ================================================


    def actu_Tabledata(self, value, seq_dirname= None, seq_dir= None, seq_identifier= None):
        seq_dir = get_project_variable("QS2_seq_dir") or seq_dir
        if not seq_dir:
            return
        
        self.cb_dataType.setEnabled(True)
        self.parca_layer = seq_read("parca", seq_dir)
        self.ua_layer = seq_read("ua", seq_dir)

        if value == "Vérificateur de données":
            self.check_data(seq_dir)
            self.current_layer = self.ua_layer
            self.current_layer = self.get_or_load_layer("ua", seq_dir, 
                                                        group="SEQUOIA", style_folder=get_project_variable("QS2_styles_directory"))

            self.ua_layer = self.current_layer
            self._setup_ui_verif()
            self.populate_cb_from_field(cb_name = "cb_parcelle", Layer = self.ua_layer, field_name = "N_PARFOR")
            self.populate_cb_from_field(cb_name = "cb_sspf", Layer = self.ua_layer, field_name = "N_SSPARFOR")

        elif value == "Synthèse":
            try:
                synthese = seq_read("summary", seq_dir)
                self.final_layer = self.setFinaldata(seq_dir, synthese)
                self.current_layer = self.final_layer

                self.populate_cb_from_field(cb_name = "cb_parcelle", Layer = self.final_layer, field_name = "N_PARFOR")
                self._setup_ui_synthese()
                self.fill_table(self.final_layer, list(self.final_layer.getFeatures()))
            except Exception as e:
                messageLog(f"Erreur lors de la mise à jour de la table : {e}", "w")
                
        
        elif value == "Sélectionner une table":
            self.setup_ui_selection()

    # ================================================
    # création de la synthèse
    # ================================================

    def setFinaldata(self, seq_dir, synthese):
        """"""
        source = synthese.dataProvider().dataSourceUri()
        synthese = source.split("|")[0]

        final_data = getFinaldata(synthese)

        return final_data

    # ================================================
    # tableaux : Vérification
    # ================================================

    def check_data(self, seq_dir):

        self.forestTable.clearContents()
        self.forestTable.setRowCount(0)

        self.fill_table(self.ua_layer, list(self.ua_layer.getFeatures()))


    # endregion
    # ================================================
    # region utilitaires tableaux
    # ================================================ 
    
    # Utilitaire pour UI 
    def _setup_ui_verif(self):
        self.forestTable.setHidden(False)
        self.cb_parcelle.setEnabled(True)
        self.cb_sspf.setEnabled(True)
        self.cb_sspf.setHidden(False)
        self.lbl_sspf.setHidden(False)


    def _setup_ui_synthese(self):
        self.forestTable.setHidden(False)
        self.cb_parcelle.setEnabled(True)
        self.cb_sspf.setHidden(True)
        self.lbl_sspf.setHidden(True)

    def setup_ui_selection(self):
        self.cb_parcelle.setEnabled(False)
        self.cb_sspf.setEnabled(False)
        self.forestTable.setHidden(True)

    # Utilitaire pour remplir les comboBox de sélection
    def populate_cb_from_field(self, cb_name, Layer, field_name):

        cb = getattr(self, cb_name)
        values = sorted({str(f[field_name]) for f in Layer.getFeatures()})
        cb.clear()
        cb.addItem("Toutes")      # valeur par défaut
        cb.addItems(values)
        cb.setCurrentIndex(0)


    def on_cb_parcelle_changed(self, value):

        layer = self.current_layer

        expr = self.buildExpression(layer, value)

        if expr:
            ids = self.selectFeaturesByExpression(layer, expr)

            if ids is not None:
                self.update_table_with_selection(layer, ids)

        else:
            self.update_table_with_all(layer)


    def update_table_with_all(self, layer):
        feats = list(layer.getFeatures())
        self.fill_table(layer, feats)

    def update_table_with_selection(self, layer, ids):
        feats = [f for f in layer.getFeatures() if f.id() in ids]
        self.fill_table(layer, feats)
    

    def fill_table(self, layer, features):
        """Remplit la table avec les features données"""

        fields = layer.fields()

        self.forestTable.setColumnCount(len(fields))
        self.forestTable.setHorizontalHeaderLabels([f.name() for f in fields])
        self.forestTable.setRowCount(len(features))

        # met en forme la table
        self.TableFormat()

        for row, feat in enumerate(features):
            for col, field in enumerate(fields):
                val = feat[field.name()]
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.forestTable.setItem(row, col, item)

    def TableFormat(self):
        """Met en forme la table"""
        header = self.forestTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.forestTable.setAlternatingRowColors(True)



    def buildExpression(self, layer, value):

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
    
    # utile pour éviter de charger plusieurs fois les couches dans le projet + 
    # permet la selection d'entités dans la couche UA importé  de ADD_DATA
    def get_or_load_layer(self, key, seq_dir, group="SEQUOIA", style_folder=None):

        meta = seq_layer(key)
        layer_name = meta["name"]

        project = QgsProject.instance()

        for lyr in project.mapLayers().values():
            if lyr.name() == layer_name:
                return lyr

        layer = seq_read(
            key,
            seq_dir,
            add_to_project=True,
            group_name=group,
            style_folder=style_folder
        )

        return layer

