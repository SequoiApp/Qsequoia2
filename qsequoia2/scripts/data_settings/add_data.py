# region IMPORT

# region IMPORT
"""
Module 4 : add_data

Ce module gère l’interface utilisateur pour ajouter des données dans le projet QGIS.

Fonctionnalités principales :
- Affiche les vecteurs, rasters, services web et bases de données dans des onglets
- Permet d’ajouter les couches au projet avec leur style
- Gère la création de groupes et l’organisation des couches
- Lit les fichiers YAML de configuration pour alimenter les arborescences

Classe principale :
- AddDataDialog : QDialog qui contient toute la logique métier pour l’ajout de données.

Auteur : Alexandre Le Bars - Comité des Forêts
        Paul Carteron - Racines experts forestiers associés
        Matthieu Chevereau - Caisse des dépôts et consignation
Email : alexlb329@gmail.com

"""

import importlib
from PyQt5.QtWidgets import QDialog, QMessageBox, QFileDialog
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem

import os
import yaml

from qsequoia2.scripts.tools_settings.PY.unload import unknown_data



from .add_data_dialog import Ui_AddDataDialog



# Import from utils folder

from qsequoia2.scripts.utils.add_vector_layers import load_vectors
from qsequoia2.scripts.utils.add_raster_layers import load_rasters
from qsequoia2.scripts.utils.add_wmts_layers import load_wmts
from qsequoia2.scripts.utils.config import *

# endregion

# region ClASSDATADIALOG


class AddDataDialog(QDialog):
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
        ui : instance de Ui_AddDataDialog
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

        self.ui = Ui_AddDataDialog()
        self.ui.setupUi(self)
        self.add_tree_tab()
        self.dock = parent


        # Connexion des signaux après setupUi
        self.treeVECTOR.itemClicked.connect(self.on_item_clicked)
        self.treeRASTOR.itemClicked.connect(self.on_item_clicked)
        self.treeHECTOR.itemClicked.connect(self.on_item_clicked)
        self.treeCASTOR.itemClicked.connect(self.on_item_clicked)
        # etc.



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
        self.treeVECTOR.setObjectName("treeVECTOR")
        self.treeVECTOR.setHeaderLabels(["Vecteurs disponibles"])

        # 3) ajout des items en lisant le yaml
        script_dir = os.path.dirname(__file__)
        yaml_path = os.path.join(script_dir, "..","..","inst","seq_layers.yaml")

        with open(yaml_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

            categories = {}

            for key, entry in data.items():
                name = entry.get('name', "")
                ext = entry.get('ext', "")

                # On ne garde que geojson ou gpkg
                if ext not in ["geojson","gpkg","shp","kml"]:
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
        self.ui.tabWidget.addTab(tab, "VECTEURS")

        # Widget Rasters

        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.treeRASTOR = QTreeWidget()
        self.treeRASTOR.setObjectName("treeRASTOR")
        self.treeRASTOR.setHeaderLabels(["Rasters disponibles"])

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
        self.ui.tabWidget.addTab(tab, "RASTERS")

        # Widget Services Web

        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.treeHECTOR = QTreeWidget()
        self.treeHECTOR.setObjectName("treeHECTOR")
        self.treeHECTOR.setHeaderLabels(["Services Web disponibles"])

        yaml_path = os.path.join(script_dir, "..","..","inst","qseq_URLS.yaml")
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
        self.ui.tabWidget.addTab(tab, "WMS/WFS")

        # Widget Bases de Données
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.treeCASTOR = QTreeWidget()
        self.treeCASTOR.setHeaderLabels(["Bases de Données disponibles"])
        # (code to read YAML and populate tree would go here)
        layout.addWidget(self.treeCASTOR)
        self.ui.tabWidget.addTab(tab, "BASES DE DONNÉES")

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

        print(f"Clic sur '{label}' depuis l’arbre : {tree.objectName()}")

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

        print(f"\n[add_data] => Clic sur l'item : {label}")


        current_tab = self.ui.tabWidget.tabText(self.ui.tabWidget.currentIndex())
        # --- Détection automatique des sections (items parents) ---
        if item is not None and item.parent() is None:
            print(f"\n[add_data] => Clique sur une section : {label}")
            return


        # --- Vérifications projet ---
        if current_tab =="WMS/WFS":
            pass

        elif not self.current_project_name or self.current_project_name in [
            "Nom du projet - doit être le même que CARTO FUTAIE ou RSEQUOIA",
            "DefaultProject"]:
            QMessageBox.information(
                self,
                "Nom absent",
                "Merci de renseigner le nom du projet."
            )
            return

        if not self.current_style_folder:
            QMessageBox.information(
                self,
                "Kartenn",
                "Pas de dossier de styles sélectionné, veuillez cliquer sur 🔧."
            )
            return



        # --- Appel dynamique ---

        # Pour les WMTS

        if current_tab == "WMS/WFS":
            load_wmts([label])

        # Pour les Rasters

        elif current_tab == "RASTERS":
            if current_tab == "WMS/WFS":
                pass
            if self.current_project_folder is None:

                layer_paths = {}

                files, _ = QFileDialog.getOpenFileNames(
                    parent=self,
                    caption="Pas de dossier de projet, sélectionnez une couche",
                    directory="",
                    filter="Couches raster (*.tif *.tiff *.png)"
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
            if current_tab =="WMS/WFS":
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
                    parent=self)
             
            # TODO : ne pas lancer load_vectors si layer vient des dosssier de mises en pages "LAYOUT" (ex : SEQ_PF_poly) pour éviter les doublons
            if layer_paths:
                load_vectors(
                    layer_paths,
                    project_name=self.current_project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    parent=self)
            if not layer_paths:
                QMessageBox.information(self,"Couche non trouvée",f"Aucune couche trouvée pour {label} dans le dossier de projet.")


