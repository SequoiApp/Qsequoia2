
# ==========================================================================
# import
# ==========================================================================

# python 

from pathlib import Path
import os, json

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.core import *
from PyQt5.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt5.QtCore import QTimer, Qt

# Qsequoia2 

from ..utils.messageBar import *
from .forest_get_data import getForestdata
from .get_final_data import getFinaldata
from ..utils.variable import *
from ..utils.seq_config import *
from ..utils.yaml_helper import *
from ..utils.seq_config import *

UI_PATH = Path(__file__).parent / 'forest_data.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

# ==========================================================================
# ForestDataDialog
# ==========================================================================

class ForestDataDialog(QDialog, FORM_CLASS):
    """Classe principale du module Forestdata de Qsequoia2"""
    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.setupUi(self)
        # Chargement des variables
        self.seq_dir = get_project_variable("QS2_seq_dir")
        self.seq_identifier= get_project_variable("QS2_seq_identifier")
        self.current_style_folder = get_global_variable("QS2_styles_directory")
        
        # appel de la fonction de refresh
        self.actu.clicked.connect(self.actu_data)

        # réaction au changement du numéro de parcelle dans le tableau
        self.cb_parcelle.currentTextChanged.connect(self.on_cb_parcelle_changed)

    def actu_data(self):
        """relance les fonctions de chargement des data pour actualiser l'affichage"""
        if not self.seq_dir :
            messageBar(self.iface,"Pas de dossier de projet !","w",10)
            return
        self.get_base_metadata()

        # lecture des metadata
        self.metadata = yaml_loader("Qseq_forestMetadata","metadata")
        print(self.metadata)

        self.display_base_metadata()
        try:
            self.setFinaldata()
        
        except Exception as e :
            messageBar(self.parent,e,"w",10)


    def get_base_metadata(self):
        # appel du calcul des metadonnées
        seq_metadata = self.run_calculation()
        self.save_metadata(seq_metadata)


    def run_calculation(self):
        #try : 
        seq_metadata = getForestdata(
            seq_identifier=self.seq_identifier,
            seq_dir=self.seq_dir,
            iface=self.iface)
        return seq_metadata.build()
        
        #except Exception as e :
            #messageBar(self.iface, f"Erreur lors de la construction des metadata : {e}","w",10)
            #return {"vide"}
        
    def save_metadata(self, seq_metadata):
        try:
            yaml_creator("Qseq_forestMetadata", seq_metadata)  
            messageLog(f"-- metadata build pour {self.seq_dir} --!","i")
        except Exception as e:
            messageBar(self.iface, f"Erreur lors de l'export : {e}", "w", 10)


    def display_base_metadata(self):

        if "forest_name" in self.metadata:
            forest_name = self.metadata.get("forest_name", self.project_name)
        else : 
            forest_name = self.project_name

        departement_str = self.metadata.get("departement_str", "")
        city_str = self.metadata.get("city_str", "")
        surface_formatted = self.metadata.get("surface_formatted","")
        surface_boisee_ha = self.metadata.get("surface_boisee_ha","")
        surface_non_boisee_ha = self.metadata.get("surface_non_boisee_ha","")
        owner_str = self.metadata.get("owner_str","")

        self.forest_name_edit.setText(str(forest_name))
        self.departement_edit.setText(str(departement_str))
        self.city_edit.setText(str(city_str))
        self.surface_edit.setText(str(surface_formatted))
        self.surface_boisee_edit.setText(str(surface_boisee_ha))
        self.surface_non_boisee_edit.setText(str(surface_non_boisee_ha))
        self.owner_edit.setText(str(owner_str))



    def setFinaldata(self):
        synthesePath = self.findSynthese()

        if not synthesePath:
            return
        
        synthesePath = str(synthesePath)

        data = getFinaldata(synthesePath)

        # Stocker la couche mémoire pour les sélections
        self.final_layer = data

        # Remplir la combo des parcelles
        self.populate_cb_parcelle(data)

        # --- Remplir le tableau ---
        fields = data.fields()
        features = list(data.getFeatures())

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


    # fonction provisoire pour trouver la synthèse de finalisation

    def findSynthese(self):
        name = "SYNTHESE"

        # Parcourir tous les fichiers du dossier
        for file in Path(self.current_project_folder).iterdir():
            if file.is_file() and name in file.name:
                return file  # retourne un Path complet

        return None  # si rien trouvé










