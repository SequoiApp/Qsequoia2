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
    def __init__(self, plugin, parent=None):
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

        
        # Charger les paramètres existants
        self.load_settings()



        # Connecter le bouton OK
        self.buttonBox.accepted.connect(self.save_settings)
        self.stylesButton.clicked.connect(self.select_styles_directory)
        self.modelsButton.clicked.connect(self.select_models_directory)
        self.folders_folder_button.clicked.connect(self.select_folders_folder)


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
        styles_dir = get_global_variable("styles_directory") or ""
        self.stylesInput.setText(styles_dir)
            
        # Répertoire de modèles
        models_dir = get_global_variable("models_directory") or ""
        self.modelsInput.setText(models_dir)
        
        # Utilisateur
        user = get_global_variable("user_full_name")
        self.userInput.setText(user)

        # Organisation

        orga_name = get_global_variable("organisation")
        self.orga.setText(orga_name)

        # Adresse de l'organisation

        adress = get_global_variable("adress_organisation")
        self.adress.setText(adress)

        self.open_maps.clicked.connect(lambda : open_maps(adress))

        QS2_default_project_state = get_global_variable("QS2_default_project")

        if not QS2_default_project_state:
            self.open_project.setChecked(False)
        else:
            self.open_project.setChecked(True)

        # Proposition des projets

        folders_folder = get_global_variable("folders_folder")
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
        

        set_global_variable("styles_directory", styles_dir)
        set_global_variable("models_directory", models_dir)
        set_global_variable("user_full_name", user)
        set_global_variable("adress_organisation", adress)
        set_global_variable("organisation", orga_name)
        set_global_variable("QS2_default_project", QS2_default_project)
        set_global_variable("folders_folder", folders_folder )
        set_global_variable("QS2_suggest_project", QS2_suggest_project )
        
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
    



    