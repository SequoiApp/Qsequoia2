
# ==========================================================================
# import
# ==========================================================================

# python 

from pathlib import Path
import os, json
import re

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import *
from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView
from PyQt5.QtCore import Qt

# Qsequoia2 

from ..utils.messageBar import *
from .forest_get_data import getForestdata
from .data_table import getFinaldata
from ..utils.variable import *
from ..utils.seq_config import *
from ..utils.yaml_helper import *
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

        # réaction au changement du numéro de parcelle dans le tableau
        self.cb_parcelle.currentTextChanged.connect(self.on_cb_parcelle_changed)

        self.forestType_checkbox = {
            self.checkBox_domaine: "Domaine",
            self.checkBox_massif: "Massif",
            self.checkBox_foret: "Forêt",
            self.checkBox_bois: "Bois"
        }

        for cb in self.forestType_checkbox:
            cb.setVisible(False)
            cb.toggled.connect(self.on_checkbox_toggled)

    # endregion
    # ================================================
    # region Actualisation et construction des metadonnées
    # ================================================


    def actu_data(self, seq_dirname, seq_dir, seq_identifier):
        """relance les fonctions de chargement des data pour actualiser l'affichage"""  
        seq_dir = Path(seq_dir)

        if not seq_dir :
            messageBar(self.iface,"Pas de dossier de projet !","w",10)
            return
        
        for cb in self.forestType_checkbox:
            cb.setVisible(True)
        
        # création des métadata 
        seq_metadata = self.run_calculation(seq_dir)
        self.export_to_project_variables(seq_metadata, seq_dir)

        # lecture des metadata
        self.get_base_metadata()
        self.display_base_metadata()

        # Lecture des données finales
        self.setFinaldata(seq_dir)

    def run_calculation(self, seq_dir):
        try : 
            seq_metadata = getForestdata(self.iface, seq_dir)

            return seq_metadata.build()

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

    # endregion
    # ================================================
    # region Lecture et affichage
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

        self.update_forest_name(seq_identifier)


    def update_forest_name(self, seq_identifier):
        """Met à jour le nom de la forêt en combinant le nom du projet et le type de propriété sélectionné."""

        prefix = next((label for cb, label in self.forestType_checkbox.items() if cb.isChecked()), "")

        base = seq_identifier

        base = re.sub(r"^(ST|STE|SAINT)(.*)", r"\1 \2", base, flags=re.IGNORECASE)

        base = (base.lower().replace("_", " ").replace(".", " ").replace("-", " ").title().split())
        co = ["De", "La", "D", "Le"]
        ST = ["ST", "STE", "SAINT"]
        base = [elem.title() if elem in ST else elem for elem in base]

        base = [elem.lower() if elem in co else elem for elem in base]
        base = " ".join(base)
        
        if prefix and base:
            # plural names take " des "
            if base.lower().endswith("s"):
                connector = " des "
            # then vowel or mute-h → d'
            elif base[0].lower() in ("a","e","i","o","u","h"):
                connector = " d'"
            # otherwise normal " de "
            else:
                connector = " de "
            forest_name = f"{prefix}{connector}{base}"
        else:
            forest_name = base

        set_project_variable("QS2_forest_name", forest_name)

        self.forest_name_edit.setText(str(forest_name))


    # endregion
    # ================================================
    # region tableaux : finalisation
    # ================================================

    def setFinaldata(self, seq_dir):
        """"""
        synthese = seq_read("summary", seq_dir)
        source = synthese.dataProvider().dataSourceUri()
        synthese = source.split("|")[0]

        if not synthese:
            self.table = {
                self.label_2,
                self.cb_parcelle,
                self.forestTable}

            for elements in self.table:
                elements.setVisible(False)
                return
        

        final_data = getFinaldata(synthese)

        # Stocker la couche mémoire pour les sélections
        self.final_layer = final_data

        # Remplir la combo des parcelles
        self.populate_cb_parcelle(final_data)

        fields = final_data.fields()
        features = list(final_data.getFeatures())

        self.forestTable.setColumnCount(len(fields))
        self.forestTable.setHorizontalHeaderLabels([f.name() for f in fields])
        self.forestTable.setRowCount(len(features))

        for row, feat in enumerate(features):
            for col, field in enumerate(fields):
                value = feat[field.name()]
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.forestTable.setItem(row, col, item)

        header = self.forestTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.forestTable.setAlternatingRowColors(True)

    
    def populate_cb_parcelle(self, data):
        # Récupérer les valeurs uniques
        values = sorted({str(f["N_PARFOR"]) for f in data.getFeatures()})

        self.cb_parcelle.clear()
        self.cb_parcelle.addItem("Toutes")      # valeur par défaut
        self.cb_parcelle.addItems(values)

        self.cb_parcelle.setCurrentIndex(0)  


    def on_cb_parcelle_changed(self, value):
        layer = self.final_layer  # ta couche mémoire

        layer.removeSelection()

        # Si "Toutes" → aucune sélection → afficher tout
        if value == "Toutes":
            self.update_table_with_all(layer)
            return

        # Sinon → sélection attributaire
        expr = f"\"N_PARFOR\" = '{value}'"
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
        fields = layer.fields()

        self.forestTable.setColumnCount(len(fields))
        self.forestTable.setHorizontalHeaderLabels([f.name() for f in fields])
        self.forestTable.setRowCount(len(features))

        for row, feat in enumerate(features):
            for col, field in enumerate(fields):
                val = feat[field.name()]
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.forestTable.setItem(row, col, item)

    # endregion
    # ================================================
    # region tableaux : Vérification
    # ================================================