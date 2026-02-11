import os
import yaml

from dataclasses import dataclass, field
from pathlib import Path

from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from PyQt5.QtWidgets import (QDialog,QWidget,QVBoxLayout,QCheckBox,QLabel)
from qgis.core import Qgis, QgsProject, QgsMessageLog, QgsLayerTreeGroup, QgsCoordinateReferenceSystem, QgsMapThemeCollection
from qgis.utils import iface

from qsequoia2.scripts.utils.layers import resolve_layer_name


from .project_settings_dialog import Ui_ProjectSettingsDialog


# Import from utils folder
from .project_config import ProjectConfig
from .project_settings_service import compute_layout_info, import_layout, configure_layout
from ..utils.layers import configure_snapping 
from .layout import ProjectBuilder
from ..utils.variable import set_project_variable



class ProjectSettingsDialog(QDialog, Ui_ProjectSettingsDialog):

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self,current_project_name,current_style_folder,downloads_path,current_project_folder,iface,parent=None):
        super().__init__(parent)

        self.iface = iface

        self.current_project_name = current_project_name
        self.current_style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.current_project_folder = current_project_folder

        self.setupUi(self)

        # YAML principal
        self.yaml_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "inst", "project.yaml")
        )

        # Liste des projets
        self.projects_list = self.get_current_project_type(self.yaml_path)

        # ComboBox
        self.comboBox_projects.addItem("")
        self.comboBox_projects.addItems(self.projects_list)
        self.comboBox_projects.setCurrentIndex(0)

        # Connexions
        self.comboBox_projects.currentIndexChanged.connect(self._on_project_changed)
        self.comboBox_projects.currentTextChanged.connect(self.update_scale)
        self.layout.clicked.connect(self.accept)


        self.config = ProjectConfig(self.yaml_path)


    # ==========================================================
    # PROJECT TYPES
    # ==========================================================

    def get_current_project_type(self, yaml_path):
        """Retourne les types de projets disponibles depuis project.yaml"""

        if not os.path.exists(yaml_path):
            return []

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            return []

        return list(data.keys())

    def _get_project_key(self):
        """Retourne le projet sélectionné"""
        return self.comboBox_projects.currentText()

    # ==========================================================
    # CALLBACK PROJECT CHANGE
    # ==========================================================

    def _on_project_changed(self):
        """Quand l'utilisateur change de projet"""

        project_key = self._get_project_key()

        if project_key:
            self._layers_tab()

    # ==========================================================
    # LAYERS TAB
    # ==========================================================

    def _layers_tab(self):
        """
        Affiche les couches définies dans project.yaml
        en respectant les groupes (VECTEUR / SEQUOIA / WMTS)
        et coche celles du thème par défaut.
        """

        project_type = self._get_project_key()
        print("Chargement des couches depuis project.yaml :", project_type)

        tab = self.layers_tab
        tab.clear()

        # ================================
        # Charger la config du projet
        # ================================

        cfg = self.config._load_project().get(project_type)

        if not cfg:
            print("Projet introuvable dans project.yaml")
            return

        canvas_cfg = cfg.get("canvas", {})
        groups = canvas_cfg.get("groups", [])

        # ================================
        # Layers cochés par défaut
        # ================================

        default_layers = self.config.get_default_layers(project_type)


        # ================================
        # Création des onglets par groupe
        # ================================

        for group in groups:

            group_name = group.get("name", "Sans nom")
            layers = group.get("layers", [])

            # aplatissement si anchors YAML
            layers = self.config.flatten(layers)

            # Widget onglet
            tab_widget = QWidget()
            layout = QVBoxLayout(tab_widget)

            title = QLabel(f"<b>{group_name}</b>")
            layout.addWidget(title)

            # ================================
            # Checkboxes des layers du groupe
            # ================================

            for layer_name in layers:

                cb = QCheckBox(layer_name)
                cb.setObjectName(f"chk_{layer_name}")

                # coche si layer dans thème par défaut
                if layer_name in default_layers:
                    cb.setChecked(True)

                layout.addWidget(cb)

            layout.addStretch()

            # Ajout onglet
            tab.addTab(tab_widget, group_name)


    # ==========================================================
    # SCALE UPDATE
    # ==========================================================

    def update_scale(self, project_name: str):
        """Met à jour scaleBox selon project.yaml"""

        if not project_name:
            return

        try:
            canvas = self.config.get_project_canvas(project_name)

            if canvas.scale:
                self.scaleBox.setValue(canvas.scale)

        except Exception as e:
            print("Erreur update_scale :", e)


    

    # ==========================================================
    # Prise en compte des paramètres et acceptation du projet
    # ==========================================================


    def accept(self):

        project_key = self._get_project_key()

        if not project_key:
            QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return

        try:
            # ================================
            # 1. Variable projet
            # ================================
            set_project_variable("forest_map_project", project_key)

            # ================================
            # 2. Construire projet via la classe
            # ================================

            if self.copy_layers.isChecked():
                copy_layers = True
            else:
                copy_layers = False

            builder = ProjectBuilder(copy_layers,current_project_name=self.current_project_name,current_style_folder=self.current_style_folder,downloads_path=self.downloads_path,current_project_folder=self.current_project_folder,project_key=project_key, yaml_path=self.yaml_path,iface=self.iface)
            print(self.current_project_folder)
            builder.build()


            # ================================
            # 3. Snapping
            # ================================
            configure_snapping()

            # ================================
            # 4. Layout composeur si demandé
            # ================================
            if self.cb_composeur.isChecked():

                canvas_cfg = self.config.get_project_canvas(project_key)
                layout_cfg = self.config.get_project_layout(project_key)


                builder = ProjectBuilder(self, project_key,canvas_cfg,layout_cfg,self.iface,self.current_project_name,self.current_style_folder,self.downloads_path,self.current_project_folder)
                builder.build()
                print(self.current_project_folder)

                info = compute_layout_info(scale=canvas_cfg.scale,coeff_cadre=self.dsb_occup.value() / 100)

                layout = import_layout(
                    QgsProject.instance(),
                    info.paper_format,
                    info.orientation
                )

                if layout:
                    configure_layout(
                        QgsProject.instance(),
                        self.iface,
                        layout,
                        layout_cfg.theme,
                        canvas_cfg.scale,
                        layout_cfg.legends
                    )

                    self.iface.openLayoutDesigner(layout)

            # ================================
            # 5. Fermer la fenêtre
            # ================================
            super().accept()

        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))





