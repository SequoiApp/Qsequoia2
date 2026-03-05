import os,re
import time
import yaml, json


from pathlib import Path

from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from PyQt5.QtWidgets import (QDialog,QWidget,QVBoxLayout,QCheckBox,QLabel)
from qgis.core import Qgis, QgsProject, QgsMessageLog, QgsLayerTreeGroup, QgsCoordinateReferenceSystem, QgsMapThemeCollection
from qgis.utils import iface
from PyQt5.QtCore import QTimer

#from qsequoia2.scripts.utils.layers import resolve_layer_name


from .project_settings_dialog import Ui_ProjectSettingsDialog


# Import from utils folder
from .project_config import ProjectConfig
from .project_settings_service import LayoutService
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
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        self.metadata_path = os.path.join(self.script_dir, "..","..","data","_metadata","currentFolder","forest_metadata.json")

        self.setupUi(self)

        ## Connection des checkboxes
        self.nom_checkbox = {
            self.checkBox_domaine: "Domaine",
            self.checkBox_massif: "Massif",
            self.checkBox_foret: "Forêt",
            self.checkBox_bois: "Bois",
        }
        for cb in self.nom_checkbox:
            cb.toggled.connect(self.on_checkbox_toggled)



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

        # Connect composeur chekbox to occup percentage
        self.cb_composeur.toggled.connect(self.dsb_occup.setEnabled)
        if self.cb_composeur.isChecked():
            self.dsb_occup.setEnabled(True)

        # Mettre le boutton de mise en page en gris si pas de paramètres

        self.layout.setEnabled(False)

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

        # appel de update scale
        self.update_scale(project_key)


    # ==========================================================
    # SCALE UPDATE
    # ==========================================================

    def update_scale(self, project_name: str):
        """Met à jour scaleBox selon project.yaml
        - posibilité de modifier sa valeur manuellement
        - se reinitialise à chaque changement de projet"""

        if not project_name:
            return

        try:
            canvas = self.config.get_project_canvas(project_name)

            if canvas.scale:
                self.scaleBox.setText(f"1 / {canvas.scale}")
            

        except Exception as e:
            print("Erreur update_scale :", e)


    # =========================================================
    # Lecture et affichage des données sur la forêt
    # =========================================================


    ### gestion des checkboxs

    def on_checkbox_toggled(self, checked):
        """
        Déclenché quand l'utilisateur coche/décoche une checkbox.
        - Si pas de projet, décocher toutes.
        - Sinon, rendre les checkboxes mutuellement exclusives.
        """
        if not getattr(self, "current_project_name", None):
            # Aucun projet => décocher toutes
            for cb in self.nom_checkbox:
                if cb.isChecked():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)
            return

        if checked:
            # Une checkbox a été cochée, décocher toutes les autres
            sender_cb = self.sender()
            for cb in self.nom_checkbox:
                if cb != sender_cb and cb.isChecked():
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)

        # Mettre à jour le nom de forêt si nécessaire
        self.update_forest_name()


    ### Mise à jour du nom de la forêt

    def update_forest_name(self):

        try:
            # Charger le JSON existant
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except FileNotFoundError:
            metadata = {}
        
        base = metadata.get("project_name")

        if base != self.current_project_name:
            QMessageBox.Error(self.iface.mainWindow(),"Erreur", "Crash général")

        # find the first‐checked box (if any) and grab its label
        prefix = next((label for cb, label in self.nom_checkbox.items() if cb.isChecked()), "")

        # On met en forme la base
        
        # 1. Séparer ST collé
        base = re.sub(r"^(ST|STE|SAINT)(.*)", r"\1 \2", base, flags=re.IGNORECASE)

        # 2. Normalisation classique
        base = (
            base.lower().replace("_", " ").replace(".", " ").replace("-", " ").title().split())

        co = ["De", "La", "D", "Le"]
        ST = ["ST", "STE", "SAINT"]

        # 3. Si c'est un préfixe ST alors minuscule
        base = [elem.title() if elem in ST else elem for elem in base]

        # 4. Articles en minuscule
        base = [elem.lower() if elem in co else elem for elem in base]

        # 5. Reconstruction
        base = " ".join(base)
        

        if prefix and base:
            # plural names take " des "
            if base.lower().endswith("s"):
                connector = " des "
            # then vowel or mute-h → d'
            elif base[0].lower() in ("a","e","i","o","u","h"):
                connector = " d'"
            # otherwise normal " de "
            else:
                connector = " de "
            forest_name = f"{prefix}{connector}{base}"
        else:
            forest_name = base
            
        # --- Ajout dans le JSON existant ---

        # Ajouter forest_name
        metadata["metadata"]["forest_name"] = forest_name

        # Réécrire le JSON
        with open(self.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        
        # afficher le nom du propriétaire
        self.load_city_and_owner()

    ### Affichage des communes et des propriétaire

    def load_city_and_owner(self):
        """Charge les propriétaire et communes depuis les metadata"""
        try:
            # Charger le JSON existant
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        except FileNotFoundError:
            metadata = {}

        # On récupère les valeurs depuis le sous-dictionnaire "metadata" si existant
        meta = metadata.get("metadata", {})

        city_str = meta.get("city_str", "")
        owner_str = meta.get("owner_str", "")
        forest_name = meta.get("forest_name","")

        self.lineEdit_city.setText(city_str)
        self.lineEdit_owner.setText(owner_str)
        self.forest_name.setText(forest_name)
        self.layout.setEnabled(True)


    # ==========================================================
    # Prise en compte des paramètres et acceptation du projet
    # ==========================================================


    def accept(self):

        project_key = self._get_project_key()

        if not project_key:
            QMessageBox.warning(self, "Erreur", "Aucun projet sélectionné.")
            return
        # pour le debug on sort du try catch, mais à terme il faudrait le remettre pour éviter les plantages
        #try:
        # ================================
        # 1. Variable projet
        # ================================
        set_project_variable("forest_map_project", project_key)

        # ================================
        # 2. Construire projet via la classe
        # ================================

        #if self.copy_layers.isChecked():
            #copy_layers = True
        #else:
        copy_layers = False # Désactivé pour le moment pas stable et pas voulu dans la BETA 1

        builder = ProjectBuilder(copy_layers,current_project_name=self.current_project_name,current_style_folder=self.current_style_folder,downloads_path=self.downloads_path,current_project_folder=self.current_project_folder,project_key=project_key, yaml_path=self.yaml_path,iface=self.iface)

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

            # créer le service Layout
            layout_service = LayoutService(
                project=QgsProject.instance(),
                project_key = project_key,
                project_name=self.current_project_name,
                style_folder=self.current_style_folder,
                downloads_path=self.downloads_path,
                project_folder=self.current_project_folder,
                iface=self.iface
            )

            # 1. Calcul format + orientation
            info = layout_service.compute_layout_info(
                scale=canvas_cfg.scale,
                coeff_cadre=self.dsb_occup.value() / 100
            )

            # 1. Import layout et conserver la référence
            self.current_layout = layout_service.import_layout(project_key=project_key, fmt=info.paper_format, orient=info.orientation)

            # 2. Ajouter au layout manager (une seule fois)
            lm = QgsProject.instance().layoutManager()

            # éviter les collisions de nom, je le garde pour le dev je met une condition pour éviter erreur python si le projet existe déja
            if self.current_layout is not None:
                existing = lm.layoutByName(self.current_layout.name())
                if existing:
                    lm.removeLayout(existing)
            else :
                return

            lm.addLayout(self.current_layout)

            # 3. Configurer le layout
            layout_service.configure_layout(
                layout=self.current_layout,
                theme=layout_cfg.theme,
                scale=canvas_cfg.scale,
                legends=layout_cfg.legends
            )

            # 4. Ouvrir le designer
            self.iface.openLayoutDesigner(self.current_layout)


            # mettre l'échelle de QGIS à la version du projet
            self.iface.mapCanvas().zoomScale(canvas_cfg.scale)

            #Mettre la loupe à 100%
            self.iface.mapCanvas().setMapTool(self.iface.mapCanvas().mapTool())

        # Sauvegarde du projet courant

        def save_project():
            project = QgsProject.instance()
            QgsProject.write(project, project.fileName())

        if self.cb_save_project.isChecked():
            QTimer.singleShot(1300, save_project)  # délai pour laisser le temps à QGIS de tout configurer avant d'écrire le projet






        #except Exception as e:
        
            #print("Erreur lors de l'acceptation du projet :", e)
            #QMessageBox.warning(self, "Erreur", f"Erreur lors de l'acceptation du projet : {e}")





