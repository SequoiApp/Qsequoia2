
"""
Module : add_data

Ce module gère l’interface utilisateur pour ajouter des données dans le projet QGIS.

Fonctionnalités principales :
- Affiche les vecteurs, rasters, services web et bases de données dans des onglets
- Permet d’ajouter les couches au projet avec leur style
- Gère la création de groupes et l’organisation des couches
- Lit les fichiers YAML de configuration pour alimenter les arborescences
- Lit le fichier de configuration json dans le même dossier 

Classe principale :
- AddDataDialog : QDialog qui contient toute la logique métier pour l’ajout de données.

Auteur : Alexandre Le Bars - Comité des Forêts
        Paul Carteron - Racines experts forestiers associés
        Matthieu Chevereau - Caisse des dépôts et consignation
Email : alexlb329@gmail.com

"""
# ==========================================================================
# region import
# ==========================================================================

# python 

import importlib
import os, yaml, json

# Qgis

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog, QMessageBox, QFileDialog
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem


# Qsequoia2

#from .add_data_dialog import Ui_AddDataDialog

# Import from utils folder
from qsequoia2.scripts.utils.add_vector_layers import load_vectors
from qsequoia2.scripts.utils.add_raster_layers import load_rasters
from qsequoia2.scripts.utils.add_wmts_layers import load_wmts
from qsequoia2.scripts.utils.config import *
from ..utils.layers import configure_snapping
from ..utils.messageBar import *


# import de l'UI 

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'add_data.ui'))

# endregion
# ==========================================================================
# region ClASSDATADIALOG
# ==========================================================================

class AddDataDialog(QDialog, FORM_CLASS):
    """
    Classe principale pour l’interface d’ajout de données.

    Logique métier :
    - Initialise les onglets et les arborescences
    - Connecte les signaux des QTreeWidget pour l’ajout automatique des couches
    - Charge les couches vecteur, raster et WMTS avec style
    - Crée des groupes dans le projet si nécessaire

    Attributs :
        iface : interface QGIS
        current_project_name : nom du projet courant
        current_style_folder : dossier des styles
        downloads_path : dossier de téléchargement
        current_project_folder : dossier du projet
        dock : parent QDialog

    Méthodes principales :
        add_tree_tab() : initialise les QTreeWidgets et les onglets
        on_item_clicked(item, column) : callback sur clic d’un item
        whats_layers(item, label, column) : détermine le type de couche et appelle la fonction de chargement appropriée

    """

    def __init__(self, current_project_name, current_style_folder, downloads_path, current_project_folder, iface, parent=None):
        """
        Initialise le module AddDataDialog, connecte les signaux des QTreeWidgets.

        Args:
            current_project_name (str)
            current_style_folder (str)
            downloads_path (str)
            current_project_folder (str)
            iface : interface QGIS
            parent : QWidget optionnel
        """
        super().__init__(parent)
        self.iface = iface
        self.current_project_name = current_project_name
        self.current_style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.current_project_folder = current_project_folder

        self.setupUi(self)

        # Chargement des paramètres

        self.script_dir = os.path.dirname(__file__)
        json_path = os.path.join(self.script_dir, "add_data.json")

        with open(json_path, "r", encoding="utf-8") as f:
            self.setting = json.load(f)

        self.add_tree_tab()
        self.dock = parent

        # Connexion des signaux après setupUi
        self.treeVECTOR.itemClicked.connect(self.on_item_clicked)
        self.treeRASTOR.itemClicked.connect(self.on_item_clicked)
        self.treeHECTOR.itemClicked.connect(self.on_item_clicked)


    def add_tree_tab(self):
        """
        Crée et remplit les onglets du dialogue.

        Onglets créés :
        - VECTEURS : lit le YAML seq_layer et affiche les couches vectorielles geojson disponibles
        - RASTERS : lit le YAML seq_layer et affiche les rasters tif disponibles
        - WMS/WFS : lit le YAML seq_layer et affiche les services WMTS/WFS disponibles
        - BASES DE DONNÉES : placeholder pour les potentielles bases de données des utilisateurs
        """

        # Widget Vecteurs 

        # 1) Créer le widget qui servira d'onglet
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 2) Créer le QTreeWidget
        self.treeVECTOR = QTreeWidget()
        self.treeVECTOR.setObjectName(self.setting["add_tree_tab"]["tree_name"]["vect"])
        self.treeVECTOR.setHeaderLabels([self.setting["add_tree_tab"]["headers"]["vectors"]])

        # 3) ajout des items en lisant le yaml
        yaml_path = os.path.join(self.script_dir, "..","..","inst","seq_layers.yaml")

        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

            categories = {}

            for key, entry in data.items():
                name = entry.get('name', "")
                ext = entry.get('ext', "")

                # On ne garde que geojson ou gpkg
                if ext not in self.setting["add_tree_tab"]["vector_extensions"]:
                    continue

                category_name = name.split("_")[0] if "_" in name else name

                if category_name not in categories:
                    cat_item = QTreeWidgetItem([category_name])
                    self.treeVECTOR.addTopLevelItem(cat_item)
                    categories[category_name] = cat_item

                # Ajout de l’élément dans la catégorie
                QTreeWidgetItem(categories[category_name], [name, ext])


        # 4) Ajouter le tree dans le layout
        layout.addWidget(self.treeVECTOR)

        # 5) Ajouter l’onglet au TabWidget
        self.tabWidget.addTab(tab, self.setting["add_tree_tab"]["tabs"]["vectors"])

        # Widget Rasters

        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.treeRASTOR = QTreeWidget()
        self.treeRASTOR.setObjectName(self.setting["add_tree_tab"]["tree_name"]["rast"])
        self.treeRASTOR.setHeaderLabels([self.setting["add_tree_tab"]["headers"]["rasters"]])

        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

            categories = {}

            for key, entry in data.items():
                name = entry.get('name', "")
                ext = entry.get('ext', "")

                # On ne garde que tiff
                if ext != "tif":
                    continue

                category_name = ext

                if category_name not in categories:
                    cat_item = QTreeWidgetItem([category_name])
                    self.treeRASTOR.addTopLevelItem(cat_item)
                    categories[category_name] = cat_item

                # Ajout de l’élément dans la catégorie
                QTreeWidgetItem(categories[category_name], [name, ext])

        layout.addWidget(self.treeRASTOR)
        self.tabWidget.addTab(tab, self.setting["add_tree_tab"]["tabs"]["rasters"])

        # Widget Services Web

        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.treeHECTOR = QTreeWidget()
        self.treeHECTOR.setObjectName(self.setting["add_tree_tab"]["tree_name"]["wmts"])
        self.treeHECTOR.setHeaderLabels([self.setting["add_tree_tab"]["headers"]["wmts"]])

        yaml_path = os.path.join(self.script_dir, "..","..","inst","qseq_URLS.yaml")
        with open(yaml_path, 'r', encoding='utf-8') as file:
            WMS_data = yaml.safe_load(file)

            categories = {}

            for key, entry in WMS_data["wmts"].items():
                name = entry.get("display_name", "")
                url = entry.get("url", "")

                suffix = key.replace("wmts_", "", 1)

                # On prend le premier segment : "scan1000" → "scan"
                category_name = suffix.split("_")[0]


                if category_name not in categories:
                    cat_item = QTreeWidgetItem([category_name])
                    self.treeHECTOR.addTopLevelItem(cat_item)
                    categories[category_name] = cat_item

                # Ajout de l’élément dans la catégorie
                QTreeWidgetItem(categories[category_name], [name, url])

        layout.addWidget(self.treeHECTOR)
        self.tabWidget.addTab(tab, self.setting["add_tree_tab"]["tabs"]["services"])

    # quand on clique sur un bouton des arborescences la couche est ajoutée au projet

        
    def on_item_clicked(self, item, column):
        """
        Slot appelé lors d’un clic sur un item d’un QTreeWidget.

        Args:
            item (QTreeWidgetItem): l’élément cliqué
            column (int): la colonne cliquée
        """
        tree = self.sender()  # QTreeWidget qui a émis le signal
        label = item.text(0)
        self.whats_layers(item, label, column)

    def whats_layers(self, item, label, column):
        """
        Détecte la couche sélectionnée et la charge dans QGIS.

        Vérifie :
        - Si le projet et le dossier de styles sont renseignés
        - L’onglet courant (Vecteurs, Rasters, WMTS)
        - Appelle dynamiquement `get_path` pour trouver la couches puis `load_vectors`, `load_rasters` ou `load_wmts`

        Args:
            item (QTreeWidgetItem): l’élément cliqué
            label (str): label de l’élément
            column (int): index de la colonne cliquée
        """

        messageLog(f"\n[add_data] => Clic sur l'item : {label}", "i")


        current_tab = self.tabWidget.tabText(self.tabWidget.currentIndex())
        # --- Détection automatique des sections (items parents) ---
        if item is not None and item.parent() is None:
            return


        # --- Vérifications projet ---
        if current_tab == self.setting["add_tree_tab"]["tabs"]["services"]:
            pass

        elif not self.current_project_name or self.current_project_name in [
            "Nom du projet - doit être le même que CARTO FUTAIE ou RSEQUOIA","DefaultProject"]:

            QMessageBox.information(self,"Nom absent","Merci de renseigner le nom du projet.")
            return

        if not self.current_style_folder:
            QMessageBox.information(self,"Kartenn","Pas de dossier de styles sélectionné, veuillez cliquer sur 🔧.")
            return


        # --- Appel dynamique ---

        # Pour les WMTS

        if current_tab == self.setting["add_tree_tab"]["tabs"]["services"]:
            load_wmts([label])

        # Pour les Rasters

        elif current_tab == self.setting["add_tree_tab"]["tabs"]["rasters"]:
            if current_tab == self.setting["add_tree_tab"]["tabs"]["services"]:
                pass
            if self.current_project_folder is None:

                layer_paths = {}

                files, _ = QFileDialog.getOpenFileNames(
                    parent=self,
                    caption="Pas de dossier de projet, sélectionnez une couche",
                    directory="",filter="Couches raster (*.tif *.tiff *.png)")

                if files:
                    # Cas normal : un seul label → une seule couche
                    layer_paths[label] = files[0]

            else:
                layer_paths = get_path(
                    label,
                    project_name=self.current_project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    parent=self)

            if layer_paths:
                load_rasters(
                    layer_paths,
                    project_name=self.current_project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    parent=self
                )
            if not layer_paths:
                QMessageBox.information(self,"Couche non trouvée",f"Aucune couche trouvée pour {label} dans le dossier de projet.")


        # Pour les vecteurs

        else:
            if current_tab == self.setting["add_tree_tab"]["tabs"]["services"]:
                pass
            elif self.current_project_folder is None :

                layer_paths = {}

                files, _ = QFileDialog.getOpenFileNames(
                    parent=self,
                    caption="Pas de dossier de projet, sélectionnez une couche",
                    directory="",
                    filter="Couches vecteur (*.shp *.gpkg *.geojson)"
                )

                if files:
                    # Cas normal : un seul label → une seule couche
                    layer_paths[label] = files[0]

            else:
                layer_paths = get_path(
                    label,
                    project_name=self.current_project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    parent=self,layout_mode=1)
             
            if layer_paths:
                load_vectors(
                    layer_paths,
                    project_name=self.current_project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    parent=self)
                
                # Accrochage auto sur les couches importés

                configure_snapping()

            if not layer_paths:
                QMessageBox.information(self,"Couche non trouvée",f"Aucune couche trouvée pour {label} dans le dossier de projet.")


