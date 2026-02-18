
"""
Module forest_stat : Calcul des statistiques forestières

Le module forest_stat permet de calculer de manières dynamiques les statistiques sur la forêt
en fonction des données présentes dans les couches du dossier
Le module et sa classe sont appélés lorsque watchdog détecte l'arrivé d'une nouvelle couche dans le dossier de projet

Les statistiques données sont stockées sous formes de tables json, 
la fonction down_data permet un export de ces données en format xlsx




Auteur : Alexandre Le Bars - Comité des Forêts
        Paul Carteron - Racines experts forestiers associés
        Matthieu Chevereau - Caisse des dépôts et consignation
Email : alexlb329@gmail.com

"""
# region IMPORT
import json
import importlib
from PyQt5.QtWidgets import QDialog, QMessageBox, QFileDialog
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem

from ..utils.config import get_path
from .forest_get_data import getForestdata

import os
import yaml



# Import from utils folder


# endregion

# region STAT


class ForestStat:
    """Classe ForestStat : Calcul des statistiques forestières
    chaques fonctions vise à remplir le json contenant les statistiques"""

    def __init__(self, project, project_name, project_folder, style_folder,iface):

        self.project_name = project_name
        self.project_folder = project_folder
        self.style_folder = style_folder

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(self.script_dir, "forest_data.json")

        self.init_json()

        # remplir directement le nom
        self.forest_name()

        self.forest_get_data = getForestdata(project_name, project_folder, style_folder,iface) 


    # -----------------------------
    # JSON CORE
    # -----------------------------

    def init_json(self):
        """Crée un JSON propre au début du projet"""

        base = {
            "forêt": {},
            "occupation": [],
            "stats": {}
        }

        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(base, f, indent=4, ensure_ascii=False)


    def update_json(self, section, key, value):
        """Met à jour une partie du JSON"""

        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data[section][key] = value

        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


    def add_row(self, section, row_dict):
        """Ajoute une ligne dans une liste (occupation, parcelles, etc.)"""

        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data[section].append(row_dict)

        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)


    # -----------------------------
    # STATS FUNCTIONS
    # -----------------------------

    def forest_name(self):
        """Stocke le nom de la forêt"""

        self.update_json("forêt", "nom", self.project_name)

        print("Nom de la forêt enregistré :", self.project_name)

    

    def forest_departements(self, layers, project_name, project_folder, style_folder):
        """récupère les département de la propriété"""

        base_layers = get_path(label=layers,project_name=self.project_name,project_folder=project_folder,style_folder=style_folder,parent=None)

        deps = []
        try:
            if base_layers:

                shapefile_path = list(base_layers.values())[0]

                deps = self.forest_get_data.get_grouped_values_from_shapefile(
                    shapefile_path=shapefile_path,
                    value_field="DEP_CODE",
                    filter_field=None,
                    surface_field="SURF_CAD")

        except Exception as e:
            raise TypeError(f"erreur dans forest_departements{e}")

        return deps



        
# appel pour le dev : 

if __name__ == "__main__":
     project_name = "Forêt de GATINE"
     project_folder = "E:\\GEO_DEV_SIG\\projet\\GATINE"
     forest_stat = ForestStat(project_name, project_folder)

    

    

    