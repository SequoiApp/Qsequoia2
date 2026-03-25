
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
        self.seq_dirname = get_project_variable("QS2_seq_dirname")
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
        # création des métadata 
        seq_metadata = self.run_calculation()
        self.export_to_project_variables(seq_metadata)

        # lecture des metadata
        self.get_base_metadata()
        self.display_base_metadata()
        try:
            self.setFinaldata()
        
        except Exception as e :
            messageBar(self.iface, str(e),"w",10)


    def run_calculation(self):
        #try : 
        seq_metadata = getForestdata(
                                    iface=self.iface,
                                    seq_dir=self.seq_dir,
                                    )
        
        return seq_metadata.build()
        
        #except Exception as e :
            #messageBar(self.iface, f"Erreur lors de la construction des metadata : {e}","w",10)
            #return {"vide"}
        
    def export_to_project_variables(self, seq_metadata):
        """ajoute les données dans les varaibles projets"""
        for key, value in seq_metadata.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            set_project_variable(f"QS2_{key}", value)
        messageLog(f"-- metadata build pour {self.seq_dir} --!","i")
        #try :

        #except Exception as e:
            #messageBar(self.iface, f"Erreur lors de l'export : {e}", "w", 10)

    def get_base_metadata(self):
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
        self.surface_boisee = load_var("surface_boisee")
        self.surface_non_boisee = load_var("surface_non_boisee")
        self.surface_totale = load_var("surface_totale")
        self.surface_formatted = load_var("surface_formatted")
        self.forest_name = load_var("seq_forest_name")


    def display_base_metadata(self):
        
        if self.forest_name:
            forest_name = self.forest_name
        else : 
            forest_name = self.seq_identifier

        self.forest_name_edit.setText(str(forest_name))
        self.departement_edit.setText(str(self.dep_str))
        self.city_edit.setText(str(self.city_str))
        self.surface_edit.setText(str(self.surface_formatted))
        self.surface_boisee_edit.setText(str(self.surface_boisee))
        self.surface_non_boisee_edit.setText(str(self.surface_non_boisee))
        self.owner_edit.setText(str(self.owner_str))



    def setFinaldata(self):
        """"""
        synthese = seq_read("summary", self.seq_dir)

        if not synthese:
            return
        

        final_data = getFinaldata(synthese)

        # Stocker la couche mémoire pour les sélections
        self.final_layer = final_data

        # Remplir la combo des parcelles
        self.populate_cb_parcelle(final_data)

        # --- Remplir le tableau ---
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






