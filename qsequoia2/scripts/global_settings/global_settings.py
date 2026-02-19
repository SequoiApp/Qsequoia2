# -*- coding: utf-8 -*-



from qgis.PyQt.QtWidgets import QDialog, QFileDialog

from .global_settings_dialog import Ui_GlobalSettingsDialog
from qgis.core import QgsProject
from pathlib import Path

import yaml

# Import from utils folder
from ..utils.variable import get_global_variable, set_global_variable

from .go_to_maps import open_maps





class GlobalSettingsDialog(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.ui = Ui_GlobalSettingsDialog()
        self.ui.setupUi(self)
        self.plugin = plugin
        
        # Charger les paramètres existants
        self.load_settings()



        # Connecter le bouton OK
        self.ui.buttonBox.accepted.connect(self.save_settings)
        self.ui.stylesButton.clicked.connect(self.select_styles_directory)
        self.ui.modelsButton.clicked.connect(self.select_models_directory)


    def load_settings(self):
        
        # Répertoire de styles
        styles_dir = get_global_variable("styles_directory") or ""
        self.ui.stylesInput.setText(styles_dir)
            
        # Répertoire de modèles
        models_dir = get_global_variable("models_directory") or ""
        self.ui.modelsInput.setText(models_dir)
        
        # Utilisateur
        user = get_global_variable("user_full_name")
        self.ui.userInput.setText(user)

        # Organisation

        orga_name = get_global_variable("organisation")
        self.ui.orga.setText(orga_name)

        # Adresse de l'organisation

        adress = get_global_variable("adress_organisation")
        self.ui.adress.setText(adress)

        self.ui.open_maps.clicked.connect(lambda : open_maps(adress))

        QS2_default_project_state = get_global_variable("QS2_default_project")

        if not QS2_default_project_state:
            self.ui.open_project.setChecked(False)
        else:
            self.ui.open_project.setChecked(True)


    def save_settings(self):
        # Récupère les paramètres

        styles_dir = self.ui.stylesInput.text()
        models_dir = self.ui.modelsInput.text()
        user = self.ui.userInput.text()
        adress = self.ui.adress.text()
        orga_name = self.ui.orga.text()
        QS2_default_project = self.ui.open_project.isChecked()
        

        set_global_variable("styles_directory", styles_dir)
        set_global_variable("models_directory", models_dir)
        set_global_variable("user_full_name", user)
        set_global_variable("adress_organisation", adress)
        set_global_variable("organisation", orga_name)
        set_global_variable("QS2_default_project", QS2_default_project)
        
    #TODO lancement de la fonction de reload du plugin à l'acceptation des paramètres

    def select_styles_directory(self):
        modeles_path = QgsProject.instance().homePath() or str(Path.home())

        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire de travail", str(modeles_path))
        if dir_path:
            self.ui.stylesInput.setText(dir_path)

    def select_models_directory(self):
        modeles_path = QgsProject.instance().homePath() or str(Path.home())
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire de travail", str(modeles_path))
        if dir_path:
            self.ui.modelsInput.setText(dir_path)



    