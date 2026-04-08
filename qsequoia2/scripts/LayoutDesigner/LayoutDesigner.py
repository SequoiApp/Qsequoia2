
# ==========================================================================
# region import
# ==========================================================================

# python 

import os,re
import time
import yaml, json
from pathlib import Path

# QGIS

from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from PyQt5.QtWidgets import QDialog
from qgis.core import *
from qgis.utils import iface
from PyQt5.QtCore import QTimer, Qt
from PyQt5 import uic

# Qsequoia2

# Import from utils folder
from .ConfigLoader import ConfigLoader
from .LayoutDesigner_service import LayoutService
from ..utils.layers import configure_snapping 
from .ProjectBuilder import ProjectBuilder
from ..utils.variable import set_project_variable
from ..utils.Qmessage import messageBar
from .ConfigLoader import ConfigLoader

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'LayoutDesigner.ui'))

# endregion
# ==========================================================================
# region LayoutDesignerDialog
# ==========================================================================
"""
Module LayoutDesigner

Ce module contient la classe `LayoutDesignerDialog` et les fonctions associées
pour la configuration et la génération de layouts QGIS dans le plugin QSequoia2.

Fonctionnalités principales :
- Sélection de theme de cartes.
- Gestion des types de propriétés forestières et des checkboxes mutuellement exclusives.
- Mise à jour automatique des échelles du canevas selon le projet.
- utilisation des metadata du projet (nom de forêt, commune, propriétaire).
- Création et configuration automatique des layouts QGIS via `LayoutService`.
- Prise en compte du snapping et des paramètres du projet.
- Sauvegarde conditionnelle du projet après configuration.

Classes principales :
- `LayoutDesignerDialog` : Interface utilisateur pour configurer le layout et le composeur.

Utilitaires utilisés :
- `ConfigLoader` pour la lecture des YAML de configuration.
- `ProjectBuilder` pour l'import et la configuration des couches.
- `LayoutService` pour la création et configuration du layout.
- `configure_snapping` pour appliquer les paramètres globaux d’accrochage.

Auteur : Alexandre Le Bars, Paul Carteron, Matthieu Chevereau
Date : 2026

Notes :
- Destiné à être utilisé dans QGIS >= 3.40.
- Conçu pour le plugin QSequoia2.
- Toutes les modifications des metadata sont persistées dans le fichier JSON associé au projet.

"""

class LayoutDesignerDialog(QDialog, FORM_CLASS):

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self, current_project_name, current_style_folder, downloads_path, 
                current_project_folder, iface, parent=None):
        """
        Initialise le dialogue de configuration du layout pour un projet.

        Cette fenêtre permet à l'utilisateur de :
        - sélectionner un projet,
        - définir les types de propriétés forestières,
        - configurer la mise en page (layout) et le composeur.

        :param current_project_name: Nom du projet courant.
        :type current_project_name: str

        :param current_style_folder: Chemin du dossier contenant les styles QGIS.
        :type current_style_folder: str

        :param downloads_path: Chemin du dossier de téléchargements.
        :type downloads_path: str

        :param current_project_folder: Dossier racine du projet courant.
        :type current_project_folder: str

        :param iface: Interface QGIS pour interagir avec le GUI.
        :type iface: QgisInterface

        :param config_loader: Instance de ConfigLoader déjà initialisée.
        :type config_loader: ConfigLoader

        :param parent: Widget parent Qt (optionnel).
        :type parent: QWidget | None
        """
        super().__init__(parent)

        self.iface = iface
        self.script_dir = os.path.dirname(__file__)
        self.yaml_path = os.path.join(self.script_dir, "..","..","inst","layoutSettings.yaml")
        config_loader = ConfigLoader(str(self.yaml_path))
        self.config = config_loader


        self.current_project_name = current_project_name
        self.current_style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.current_project_folder = current_project_folder

        # Metadata / YAML déjà chargé via config_loader
        self.metadata = config_loader.metadata

        # UI
        self.setupUi(self)

        # ------------------------------------------------------
        # ComboBox projets
        # ------------------------------------------------------
        self.projects_list = self.config.get_projects()
        self.comboBox_projects.addItem("")
        self.comboBox_projects.addItems(self.projects_list)
        self.comboBox_projects.setCurrentIndex(0)

        # Connexions
        self.comboBox_projects.currentIndexChanged.connect(self._on_project_changed)
        self.comboBox_projects.currentTextChanged.connect(self.update_scale)
        self.layout.clicked.connect(self.accept)

        # ------------------------------------------------------
        # Composeur
        # ------------------------------------------------------
        self.cb_composeur.toggled.connect(self.dsb_occup.setEnabled)
        if self.cb_composeur.isChecked():
            self.dsb_occup.setEnabled(True)

        # Bouton layout grisé si pas de paramètres
        self.layout.setEnabled(False)


    # ==========================================================
    # PROJECT TYPES
    # ==========================================================

    def _get_project_key(self):
        """
        Retourne le nom du projet actuellement sélectionné dans le comboBox.

        :return: Nom du projet sélectionné.
        :rtype: str
        """
        return self.comboBox_projects.currentText()

    # ==========================================================
    # CALLBACK PROJECT CHANGE
    # ==========================================================

    def _on_project_changed(self):
        """
        Callback déclenché lorsque l'utilisateur change de projet dans la liste.

        Met à jour l'échelle du layout en fonction du projet sélectionné.

        :return: None
        """

        project_key = self._get_project_key()

        # appel de update scale
        self.update_scale(project_key)


    # ==========================================================
    # SCALE UPDATE
    # ==========================================================

    def update_scale(self, project_name: str):
        """
        Met à jour la boîte d'échelle (`scaleBox`) selon les informations
        du fichier YAML du projet.

        :param project_name: Nom du projet dont l'échelle doit être chargée.
        :type project_name: str

        :return: None
        :note: Si aucun projet n'est sélectionné ou si une erreur survient, la fonction
            ne fait rien et logge l'erreur.
        """

        if not project_name:
            return

        try:
            canvas = self.config.get_project_canvas(project_name)

            if canvas.scale:
                self.scaleBox.setText(f"1 / {canvas.scale}")
            

        except Exception as e:
            messageBar(self.iface, f"Erreur update_scale :{e}","w",10)


    # ==========================================================
    # Prise en compte des paramètres et acceptation du projet
    # ==========================================================

    def accept(self):
        """
        Prend en compte les paramètres sélectionnés et construit le projet.

        Étapes principales :
        1. Vérifie qu'un projet est sélectionné.
        2. Initialise et construit le projet via `ProjectBuilder`.
        3. Configure le snapping global via `configure_snapping`.
        4. Si le composeur est activé :
        - Calcule le format et l'orientation.
        - Importe et configure le layout.
        - Ouvre le Layout Designer QGIS.
        - Met à jour l'échelle du canevas.
        5. Si l'option de sauvegarde est cochée, enregistre le projet avec un léger délai.

        :return: None
        :raises Exception: Si aucune sélection de projet n'est effectuée.
        :note: Les exceptions internes sont loggées et peuvent être décommentées pour le debug.
        """

        project_key = self._get_project_key()

        if not project_key:
            QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return
        # pour le debug on sort du try catch, mais à terme il faudrait le remettre pour éviter les plantages
        #try:

        # ================================
        # Construire projet (import et configuration des couches)
        # ================================

        builder = ProjectBuilder(current_project_name=self.current_project_name,current_style_folder=self.current_style_folder,downloads_path=self.downloads_path,current_project_folder=self.current_project_folder,project_key=project_key, yaml_path=self.yaml_path,iface=self.iface)

        builder.build()

        # ================================
        # 3. Snapping
        # ================================
        configure_snapping()

        # ================================
        # 4. Ouvrir et construire la mise en page 
        # ================================
        if self.cb_composeur.isChecked():

            canvas_cfg = self.config.get_project_canvas(project_key)
            layout_cfg = self.config.get_project_layout(project_key)

            # créer le service Layout
            layout_service = LayoutService(
                project=QgsProject.instance(),
                project_key = project_key,
                project_name=self.current_project_name,
                style_folder=self.current_style_folder,
                downloads_path=self.downloads_path,
                project_folder=self.current_project_folder,
                iface=self.iface)
            

            # Calcul format + orientation
            info = layout_service.compute_layout_info(
                scale=canvas_cfg.scale,
                coeff_cadre=self.dsb_occup.value() / 100)

            # Import layout et conserver la référence
            self.current_layout = layout_service.import_layout(project_key=project_key, fmt=info.paper_format, orient=info.orientation)

            # Ajouter au layout manager
            lm = QgsProject.instance().layoutManager()

            # éviter les collisions de nom, je le garde pour le dev je met une condition pour éviter erreur python si le projet existe déja
            if self.current_layout is not None:
                existing = lm.layoutByName(self.current_layout.name())
                if existing:
                    lm.removeLayout(existing)
            else :
                return

            lm.addLayout(self.current_layout)

            # Configurer le layout
            layout_service.configure_layout(
                layout=self.current_layout,
                theme=layout_cfg.theme,
                scale=canvas_cfg.scale,
                legends=layout_cfg.legends
            )

            # Ouvrir le designer
            self.iface.openLayoutDesigner(self.current_layout)


            # mettre l'échelle de QGIS à la version du projet
            self.iface.mapCanvas().zoomScale(canvas_cfg.scale)

            #Mettre la loupe à 100%
            self.iface.mapCanvas().setMapTool(self.iface.mapCanvas().mapTool())


        #except Exception as e:
        
            #messageBar(self.iface, f"Echec de la mise en page {e}","critical", 10)





