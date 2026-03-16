
# ==========================================================================
# region import
# ==========================================================================

# python 

from pathlib import Path
import os, json

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.core import *
from PyQt5.QtWidgets import QLabel, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import QTimer, Qt

# Qsequoia2 

from ..utils.messageBar import *
from .forest_get_data import getForestdata

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'forest_data.ui'))

# endregion
# ==========================================================================
# region ForestDataDialog
# ==========================================================================

class ForestDataDialog(QDialog, FORM_CLASS):
    def __init__(self, current_project_name, current_style_folder, downloads_path, current_project_folder, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()

        self.setupUi(self)

        self.current_project_folder = current_project_folder
        self.current_style_folder = current_style_folder
        self.downloads_path = downloads_path

        # Chargement des paramètres

        self.script_dir = os.path.dirname(__file__)
        json_path = os.path.join(self.script_dir, "forest_data.json")

        with open(json_path, "r", encoding="utf-8") as f:
            self.setting = json.load(f)


        # appel de la fonction de refresh
        self.actu.clicked.connect(self.actu_data)

    @property
    def project_name(self):
        return getattr(self.parent, "current_project_name", None)


    def get_base_metadata(self):
        # Chargement des metadonnées

        metadata_path = os.path.join(self.script_dir, "..","..","data","_metadata","currentFolder","forest_metadata.json")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data_json = json.load(f)

        # Extraire la clé "metadata"
        self.metadata = data_json.get("metadata", {})
        
        if len(self.metadata) == 0:
            try:
                forest_data = getForestdata(
                    project_name=self.project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    iface=self.iface)
                
                forest_data.run_all_calculations()
            except Exception as e:
                messageLog(f"Erreur lors du calcul des metadata : {e}","w")
        
    def actu_data(self):
        """relance les fonctions de chargement des data pour actualiser l'affichage"""
        if not self.project_name:
            messageBar(self.iface,"Pas de dossier de projet !","w",10)
            return
        self.get_base_metadata()
        self.labelMeta.setText(self.display_base_metadata())
        self.display_final_data()


    def display_base_metadata(self):

        template_path = Path(__file__).parent / "html" / "metadata_display.html"

        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

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

        html = template.format(forest_name=forest_name,
                               departement_str=departement_str,
                               city_str=city_str,
                               surface_formatted=surface_formatted,
                               surface_boisee_ha=surface_boisee_ha,
                               surface_non_boisee_ha=surface_non_boisee_ha,
                                owner_str=owner_str)

        return html



    def display_final_data(self):
        """Affiche dans un onglet les données générales finale de la forêt"""










