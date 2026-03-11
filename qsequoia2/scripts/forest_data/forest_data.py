
# ==========================================================================
# region import
# ==========================================================================

# python 

from pathlib import Path
import os, json

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.core import Qgis, QgsProject


# Qsequoia2 



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
        self.project = QgsProject.instance()

        self.setupUi(self)

        # Chargement des paramètres

        self.script_dir = os.path.dirname(__file__)
        json_path = os.path.join(self.script_dir, "forest_data.json")

        with open(json_path, "r", encoding="utf-8") as f:
            self.setting = json.load(f)

        self.project_name = current_project_name

    def get_base_metadata(self,):
        # Chargement des metadonnées
        if not self.project_name:
            return
        
        metadata_path = os.path.join(self.script_dir, "..","..","data","_metadata","currentFolder","forest_metadata.json")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data_json = json.load(f)

        # Extraire proprement la clé "metadata"
        self.metadata = data_json.get("metadata", {})



    def display_base_metadata(self):
        """Récupère les metadata de base pour les afficher proprement dans l'UI"""

    def display_final_data(self):
        """Affiche dans un onglet les données générales finale de la forêt"""

    def diplay_attribute(self):
        """Permet l'affichage des données de la table attributaire UA, et la modification de cette dernière"""






