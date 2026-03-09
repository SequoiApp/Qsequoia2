# -*- coding: utf-8 -*-
# ==========================================================================
# region import
# ==========================================================================

# python 

import yaml, json, os
from pathlib import Path

# Qgis

from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from PyQt5 import uic
# QSEQUOIA2

from qgis.core import QgsProject

# Import from utils folder
from ..utils.variable import get_global_variable, set_global_variable
from ..utils.reloader import reloadQS2
from..add_on.addon_creator import addonCreator

from .go_to_maps import open_maps

# UI 
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'global_settings.ui'))

# endregion

# endregion
# ==========================================================================
# region ClASSDATADIALOG
# ==========================================================================

class GlobalSettingsDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, plugin, parent=None):
        """
        Initialise la fenêtre des paramètres globaux du plugin.

        Cette boîte de dialogue permet de configurer différents paramètres
        utilisés par le plugin, comme les dossiers de styles, de modèles
        ou les informations utilisateur.

        :param plugin: Instance principale du plugin QSequoia2.
        :type plugin: object

        :param parent: Widget parent Qt.
        :type parent: QWidget | None
        """
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.parent = parent
        self.iface = iface

        
        # Charger les paramètres existants
        self.load_settings()

        # Connecter le bouton OK
        self.buttonBox.accepted.connect(self.save_settings)
        self.stylesButton.clicked.connect(self.select_styles_directory)
        self.modelsButton.clicked.connect(self.select_models_directory)
        self.folders_folder_button.clicked.connect(self.select_folders_folder)
        self.addon.clicked.connect(self.open_addonCreator)
        self.find_addon_folder.clicked.connect(self.select_addon_folder)


    def load_settings(self):
        """
        Charge les paramètres globaux enregistrés et met à jour les champs
        de l'interface utilisateur.

        Les paramètres récupérés incluent :
        - les dossiers de styles et de modèles,
        - les informations utilisateur et organisation,
        - les options de création automatique de projet,
        - les paramètres de suggestion de dossiers de projet.

        :return: None
        """
        # Répertoire de styles
        styles_dir = get_global_variable("QS2_styles_directory") or ""
        self.stylesInput.setText(styles_dir)
            
        # Répertoire de modèles
        models_dir = get_global_variable("QS2_models_directory") or ""
        self.modelsInput.setText(models_dir)
        
        # Utilisateur
        user = get_global_variable("QS2_user_full_name")
        self.userInput.setText(user)

        # Organisation

        orga_name = get_global_variable("QS2_organisation")
        self.orga.setText(orga_name)

        # Adresse de l'organisation

        adress = get_global_variable("QS2_adress_organisation")
        self.adress.setText(adress)

        self.open_maps.clicked.connect(lambda : open_maps(adress))

        QS2_default_project_state = get_global_variable("QS2_default_project")

        if not QS2_default_project_state:
            self.open_project.setChecked(False)
        else:
            self.open_project.setChecked(True)

        # Proposition des projets

        folders_folder = get_global_variable("QS2_folders_folder")
        self.folders_folder.setText(folders_folder)

        QS2_suggest_project_state = get_global_variable("QS2_suggest_project")
        if not QS2_suggest_project_state :
            self.suggest_folder.setChecked(False)
            self.folders_folder.setEnabled(False)
            self.folders_folder_button.setEnabled(False)
        else : 
            self.suggest_folder.setChecked(True)
            self.folders_folder.setEnabled(True)
            self.folders_folder_button.setEnabled(True)

        # Dossier des Addons

        addon_folder = get_global_variable("QS2_addon_folder")
        if not addon_folder:
            self.addon.setEnabled(False)
        self.addon_folder.setText(addon_folder)



    def save_settings(self):
        """
        Enregistre les paramètres saisis dans la fenêtre de configuration.

        Les valeurs des champs de l'interface sont stockées dans les variables
        globales du plugin puis le plugin est rechargé afin d'appliquer les
        modifications immédiatement.

        :return: None
        """
        # Récupère les paramètres

        styles_dir = self.stylesInput.text()
        models_dir = self.modelsInput.text()
        user = self.userInput.text()
        adress = self.adress.text()
        orga_name = self.orga.text()
        QS2_default_project = self.open_project.isChecked()
        folders_folder = self.folders_folder.text()
        QS2_suggest_project = self.suggest_folder.isChecked()
        addon_folder = self.addon_folder.text()
        

        set_global_variable("QS2_styles_directory", styles_dir)
        set_global_variable("QS2_models_directory", models_dir)
        set_global_variable("QS2_user_full_name", user)
        set_global_variable("QS2_adress_organisation", adress)
        set_global_variable("QS2_organisation", orga_name)
        set_global_variable("QS2_QS2_default_project", QS2_default_project)
        set_global_variable("QS2_folders_folder", folders_folder )
        set_global_variable("QS2_suggest_project", QS2_suggest_project )
        set_global_variable("QS2_addon_folder", addon_folder)

        
    # lancement de la fonction de reload du plugin à l'acceptation des paramètres
        reloadQS2(plugin=self.plugin, plug = "qsequoia2")

    def select_styles_directory(self):
        """
        Ouvre une boîte de dialogue permettant de sélectionner un dossier
        contenant les styles QGIS (.qml).

        Après sélection, le chemin est inséré dans le champ correspondant.
        La fonction vérifie également que le dossier existe et contient
        au moins un fichier de style.

        :return: bool | None
        :raises: Aucun, mais affiche des messages d'avertissement si le
                dossier est invalide ou ne contient aucun style.
        """
        modeles_path = QgsProject.instance().homePath() or str(Path.home())

        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire de travail", str(modeles_path))
        if dir_path:
            self.stylesInput.setText(dir_path)

        if not dir_path.exists() or not dir_path.is_dir():
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Dossier introuvable",
                f"Le dossier indiqué n’existe pas :\n{dir_path}"
            )
            return False

        if not any(dir_path.glob("*.qml")):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Aucun style trouvé",
                f"Le dossier sélectionné ne contient aucun fichier .qml :\n{dir_path}")
            return False


    def select_models_directory(self):
        """
        Permet à l'utilisateur de sélectionner le dossier contenant les
        modèles de traitement QGIS.

        Le chemin choisi est inséré dans le champ correspondant de
        l'interface.

        :return: None
        """
        modeles_path = QgsProject.instance().homePath() or str(Path.home())
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire de travail", str(modeles_path))
        if dir_path:
            self.modelsInput.setText(dir_path)
    

    def select_folders_folder(self):
        """
        Permet de sélectionner le dossier racine utilisé pour rechercher
        ou proposer automatiquement des dossiers de projets.

        Le chemin sélectionné est enregistré dans le champ correspondant
        de l'interface.

        :return: None
        """
        work_path = QgsProject.instance().homePath() or str(Path.home())
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire de travail", str(work_path))
        if dir_path:
            self.folders_folder.setText(dir_path)
    
    def generate_addon(self):
        """affiche la fenetre de création des addons"""

        self.addon_folder_path = get_global_variable("QS2_addon_folder")

        if not self.addon_folder_path:
            self.addon_folder_path = None

        self.addon.clicked.connect(self.open_addonCreator)
    
    def select_addon_folder(self):
        """selectionne les dossiers de rangement des addons"""
        addon_path = QgsProject.instance().homePath() or str(Path.home())
        addon_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire des addon", str(addon_path))
        if addon_dir:
            self.addon_folder.setText(addon_dir)
            self.addon_folder_path = addon_dir

    def open_addonCreator(self):
        """Ouvre la fenêtre de création d'addon."""

        addon_folder = self.addon_folder.text().strip()

        if not addon_folder:
            QMessageBox.warning(self,"Dossier manquant","Veuillez sélectionner un dossier d'addons.")
            return

        self.addonCreator_dialog = addonCreator(iface=self.iface,addon_folder=addon_folder,plugin=self.plugin,parent=self)

        self.addonCreator_dialog.exec()

    



    