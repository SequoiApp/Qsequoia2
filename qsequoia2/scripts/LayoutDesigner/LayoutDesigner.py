
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
from ..utils.messageBar import messageBar
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
        # Checkboxes types de propriétés
        # ------------------------------------------------------
        self.nom_checkbox = {
            self.checkBox_domaine: "Domaine",
            self.checkBox_massif: "Massif",
            self.checkBox_foret: "Forêt",
            self.checkBox_bois: "Bois"
        }
        for cb in self.nom_checkbox:
            cb.toggled.connect(self.on_checkbox_toggled)

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


    # =========================================================
    # Lecture et affichage des données sur la forêt
    # =========================================================


    ### gestion des checkboxs

    def on_checkbox_toggled(self, checked):
        """
        Gère la sélection des checkboxes de type de propriété.

        - Si aucun projet n'est sélectionné, toutes les checkboxes sont décochées.
        - Les checkboxes sont rendues mutuellement exclusives.
        - Met à jour le nom de la forêt en fonction de la sélection.

        :param checked: État actuel de la checkbox déclenchante.
        :type checked: bool

        :return: None
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
        """
        Met à jour le nom de la forêt en combinant le nom du projet et le type
        de propriété sélectionné.

        - Applique des règles de formatage (préfixes ST, articles, majuscules/minuscules).
        - Ajoute le `forest_name` dans le fichier JSON des metadata.
        - Met à jour l'affichage des propriétaires et des communes.

        :return: None
        :raises Exception: Si le fichier JSON est manquant ou corrompu.
        """

        try:
            # Charger le JSON existant
            with open(self.config.metadata_path, 'r', encoding='utf-8') as f:
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
        with open(self.config.metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
        
        # afficher le nom du propriétaire
        self.load_city_and_owner()

    ### Affichage des communes et des propriétaire

    def load_city_and_owner(self):
        """
        Charge et affiche les informations sur la commune et le propriétaire
        depuis les metadata du projet.

        Met à jour :
        - `lineEdit_city`
        - `lineEdit_owner`
        - `forest_name` (centré et en gras)

        :return: None
        """
        try:
            # Charger le JSON existant
            with open(self.config.metadata_path, 'r', encoding='utf-8') as f:
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
        self.forest_name.setText(f"<b>{forest_name}</b>")
        self.forest_name.setAlignment(Qt.AlignCenter)
        self.layout.setEnabled(True)


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





