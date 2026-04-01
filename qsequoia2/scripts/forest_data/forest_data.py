
# ==========================================================================
# import
# ==========================================================================

# python 

from pathlib import Path
import json

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import *
from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt

# Qsequoia2 
from .update_forest_name import *
from ..utils.messageBar import *
from .forest_get_data import *
from .data_table import *
from ..utils.variable import *
from ..utils.seq_config import *

UI_PATH = Path(__file__).parent / 'forest_data.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

# ==========================================================================
# region initalisation
# ==========================================================================

class ForestDataTabs(QDialog, FORM_CLASS):
    """Classe principale du module Forestdata de Qsequoia2"""
    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.setupUi(self)

        # checkboxes de type de forêt
        self.forestType_checkbox = {
            self.checkBox_domaine: "Domaine",
            self.checkBox_massif: "Massif",
            self.checkBox_foret: "Forêt",
            self.checkBox_bois: "Bois"
        }

        for cb in self.forestType_checkbox:
            cb.setVisible(False)
            cb.toggled.connect(self.on_checkbox_toggled)

        self.forestTable.setVisible(False)

        # réaction au changement de type de données à afficher
        self.cb_dataType.currentTextChanged.connect(self.actu_Tabledata)
        # réaction au changement de parcelle sélectionnée
        self.cb_parcelle.currentTextChanged.connect(self.on_cb_parcelle_changed)
        self.cb_sspf.currentTextChanged.connect(self.on_cb_parcelle_changed)




    # endregion
    # ================================================
    # region Metadonnées
    # ================================================


    def actu_metadata(self, seq_dirname, seq_dir, seq_identifier):
        """relance les fonctions de chargement des data pour actualiser l'affichage"""  

        # métadata build

        seq_dir = Path(seq_dir)
        self.parca_layer = seq_read("parca", seq_dir)
        self.ua_layer = seq_read("ua", seq_dir)

        for cb in self.forestType_checkbox:
            cb.setVisible(True)
        self.cb_dataType.setEnabled(True)
        
        # création des métadata 
        seq_metadata = self.run_calculation(seq_dir)
        self.export_to_project_variables(seq_metadata, seq_dir)

        # lecture des metadata
        self.get_base_metadata()
        self.display_base_metadata()


    def run_calculation(self, seq_dir):
        try : 
            seq_metadata = getForestdata(self.iface, seq_dir)

            return seq_metadata.build(self.ua_layer, self.parca_layer)

        except Exception as e :
            messageBar(self.iface, f"Erreur lors de la construction des metadata : {e}","w",10)
            return {"vide"}
        
        
    def export_to_project_variables(self, seq_metadata, seq_dir):
        """ajoute les données dans les varaibles projets"""

        for key, value in seq_metadata.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            set_project_variable(f"QS2_{key}", value)

        messageLog(f"-- metadata build pour {seq_dir} --!","i")


    # ================================================
    # Metadata Lecture et affichage
    # ================================================

    def get_base_metadata(self):
        """Récupère les metadata"""

        def load_var(key):
            val = get_project_variable(f"QS2_{key}")
            try:
                return json.loads(val)
            except (TypeError, json.JSONDecodeError):
                return val

        self.city_list = load_var("city_list")
        self.city_str = load_var("city_str")
        self.owner_list = load_var("owner_list")
        self.owner_str = load_var("owner_str")
        self.dep_list = load_var("departement_list")
        self.dep_str = load_var("departement_str")
        self.wooded_surface = load_var("wooded_surface")
        self.no_wooded_surface = load_var("no_wooded_surface")
        self.total_surface = load_var("total_surface")
        self.surface_formatted = load_var("surface_formatted")
        self.forest_name = load_var("forest_name")
        self.seq_identifier = load_var("seq_identifier")


    def display_base_metadata(self):
        """Affiche les metadata"""

        self.forest_name_edit.setText(str(self.seq_identifier))
        self.departement_edit.setText(str(self.dep_str))
        self.city_edit.setText(str(self.city_str))
        self.surface_edit.setText(str(self.surface_formatted))
        self.surface_boisee_edit.setText(str(self.wooded_surface))
        self.surface_non_boisee_edit.setText(str(self.no_wooded_surface))
        self.owner_edit.setText(str(self.owner_str))        

        if self.forest_name :
            self.forest_name_edit.setText(str(self.forest_name))
            prefix = self.forest_name.split(" ")[0]
            for cb, label in self.forestType_checkbox.items():
                cb.setChecked(label == prefix)

    # endregion
    # ================================================
    # region Forest type and name
    # ================================================

    def on_checkbox_toggled(self, checked):
        """
        Gère la sélection des checkboxes de type de propriété.

        - Si aucun projet n'est sélectionné, toutes les checkboxes sont invisibles.
        - Les checkboxes sont rendues mutuellement exclusives.
        - Met à jour le nom de la forêt en fonction de la sélection.

        """
        seq_dir = get_project_variable("QS2_seq_dir")
        seq_identifier = get_project_variable("QS2_seq_identifier")

        if not checked:
            return

        if not seq_dir or not seq_identifier :
            # Aucun projet => décocher toutes
            for cb in self.nom_checkbox:
                if cb.isChecked():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)
            return
        
        seq_dir = Path(seq_dir)

        if checked:
            # Une checkbox a été cochée, décocher toutes les autres
            sender_cb = self.sender()
            for cb in self.forestType_checkbox:
                if cb != sender_cb and cb.isChecked():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

        prefix = next((label for cb, label in self.forestType_checkbox.items() if cb.isChecked()), "")
        forest_name = update_forest_name(prefix, seq_identifier)

        set_project_variable("QS2_forest_name", forest_name)

        self.forest_name_edit.setText(str(forest_name))


    # endregion
    # ================================================
    # region tableaux
    # ================================================

    def actu_Tabledata(self, value):
        seq_dir = Path(get_project_variable("QS2_seq_dir"))

        if not seq_dir:
            return

        if value == "Vérificateur de données":
            self.check_data(seq_dir)
            self.current_layer = self.ua_layer
            self.forestTable.setVisible(True)
            self.cb_parcelle.setEnabled(True)
            self.cb_parcelle.clear()
            self.cb_sspf.setEnabled(True)
            self.cb_sspf.setVisible(True)
            self.lbl_sspf.setVisible(True)
            self.populate_cb_from_field(cb_name = "cb_parcelle", Layer = self.ua_layer, field_name = "N_PARFOR")
            self.populate_cb_from_field(cb_name = "cb_sspf", Layer = self.ua_layer, field_name = "N_SSPARFOR")

        elif value == "Synthèse":
            try:
                synthese = seq_read("summary", seq_dir)
                self.final_layer = self.setFinaldata(seq_dir, synthese)
                self.current_layer = self.final_layer

                self.populate_cb_from_field(cb_name = "cb_parcelle", Layer = self.final_layer, field_name = "N_PARFOR")
                self.forestTable.setVisible(True)
                self.lbl_sspf.setVisible(False)
                self.cb_sspf.setVisible(False)
                self.cb_parcelle.setEnabled(True)
                self.fill_table(self.final_layer, list(self.final_layer.getFeatures()))
            except Exception as e:
                messageLog(f"Erreur lors de la mise à jour de la table : {e}", "w")
                
        
        elif value == "Sélectionner une table":

            self.cb_parcelle.setEnabled(False)
            self.cb_sspf.setEnabled(False)
            self.forestTable.setVisible(False)

    # création de la synthèse et affichage dans la table

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
    
    def populate_cb_from_field(self, cb_name, Layer, field_name):
        # Récupérer les valeurs uniques

        cb = getattr(self, cb_name)
        values = sorted({str(f[field_name]) for f in Layer.getFeatures()})
        cb.clear()
        cb.addItem("Toutes")      # valeur par défaut
        cb.addItems(values)
        cb.setCurrentIndex(0)


    def on_cb_parcelle_changed(self, value):

        layer = self.current_layer
        layer.removeSelection()

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
            self.update_table_with_all(layer)
            return

        expr = " AND ".join(filters)

        request = QgsFeatureRequest().setFilterExpression(expr)
        ids = [f.id() for f in layer.getFeatures(request)]

        layer.selectByIds(ids)
        self.update_table_with_selection(layer, ids)


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