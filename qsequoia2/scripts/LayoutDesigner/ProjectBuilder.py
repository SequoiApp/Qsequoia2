
# ==========================================================================
# region import
# ==========================================================================

# python 
import os,json

# QGIS
from qgis.core import *
from qgis.utils import iface

# QSEQUOIA2
from ..utils.add_vector_layers import load_vectors
from ..utils.add_raster_layers import load_rasters
from ..utils.add_wmts_layers import load_wmts

from ..utils.layers import *
from ..utils.config import *
from ..utils.messageBar import *
from .ConfigLoader import ConfigLoader

# endregion
# ==========================================================
# region PROJECT BUILDER CLASS
# ==========================================================

class ProjectBuilder:
    """
    Auteur : Alexandre Le Bars, Paul Carteron, Matthieu Chevereau
    Date : 2026

    Description :
    -------------
    Classe centralisée pour importer et configurer les couches QGIS 
    à partir de la configuration d'un projet YAML.

    Fonctionnalités principales :
    - Chargement des couches vectorielles, raster et WMTS dans des groupes.
    - Création automatique de thèmes QGIS.
    - Gestion de l'arborescence (pliage/dépliage des groupes).
    - Zoom automatique sur une couche cible.
    - Application de l'opacité pour certaines couches WMTS.

    Args:
        current_project_name (str): Nom du projet.
        current_style_folder (str): Dossier des styles QGIS.
        downloads_path (str): Dossier de téléchargement.
        current_project_folder (str): Dossier du projet.
        project_key (str): Clé du projet dans le YAML.
        yaml_path (str): Chemin vers le fichier YAML de configuration.
        iface (QgsInterface, optional): Interface QGIS. Defaults to None.
    """

    def __init__(self,current_project_name,current_style_folder,downloads_path,current_project_folder,project_key: str,yaml_path: str,iface=None):
        """
        Initialise le builder de projet, charge la configuration YAML et les alias de couches.

        Args:
            current_project_name (str): Nom du projet.
            current_style_folder (str): Dossier contenant les styles.
            downloads_path (str): Dossier des téléchargements.
            current_project_folder (str): Dossier du projet.
            project_key (str): Clé du projet pour accéder aux paramètres YAML.
            yaml_path (str): Chemin du fichier YAML.
            iface (QgsInterface, optional): Interface QGIS. Defaults to None.

        Raises:
            ValueError: Si le dossier de projet n'est pas défini.
        """
        self.project_key = project_key
        self.iface = iface
        self.project = QgsProject.instance()
        self.parent = None

        # Variables projet
        self.project_name = current_project_name
        self.style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.project_folder = current_project_folder

        # Charger YAML de projet et les config de projets
        self.config = ConfigLoader(yaml_path)

        self.canvas_cfg = self.config.get_project_canvas(project_key)
        self.layout_cfg = self.config.get_project_layout(project_key)
        
        if not self.project_folder:
            raise ValueError("project_folder est None ! Tu dois passer un chemin valide.")
        
        # Chargement des alias de couches pour les légendes
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        alias_json_path = os.path.join(self.script_dir, "..","..","inst", "alias.json")
        if os.path.exists(alias_json_path):
            with open(alias_json_path, "r", encoding="utf-8") as f:
                aliases_json = json.load(f)
                self.layer_aliases = aliases_json.get("layer_aliases", {})
        else:
            self.layer_aliases = {}


    # ==========================================================
    # LOAD GROUPS / LAYERS
    # ==========================================================

    def load_layer_and_groups(self):
        """
        Charge les couches vectorielles, raster et WMTS dans les groupes définis
        dans le YAML du projet.

        - Les groupes sont créés si inexistants.
        - Les couches déjà chargées ne sont pas doublées.
        - Les WMTS sont chargés en une seule fois par groupe.
        """

        loaders = {
            "vector": load_vectors,
            "wmts": load_wmts,
            "raster": load_rasters}

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        # Groupe racine
        root_group = root.findGroup(self.project_key) or root.addGroup(self.project_key)


        for group in self.canvas_cfg.groups:

            gtype = group.get("type")
            layers = group.get("layers") or []
            canvas_group_name = group.get("name", "Sans nom")
            subgroup = root_group.findGroup(canvas_group_name) or root_group.addGroup(canvas_group_name)

            loader = loaders.get(gtype)

            messageLog(f"Groupe chargé : {gtype}", "w")
            if not loader:
                messageLog(f"Groupe inconnu : {gtype}", "w")
                continue

            # ======================================================
            # WMTS : appeler une seule fois avec la liste
            # ======================================================
            if gtype == "wmts":
                loader(layers, group_name=canvas_group_name)
                continue

            # ======================================================
            # VECTOR
            # ======================================================

            if gtype == "vector":

                for layer_name in layers:

                    layer_paths_dict = get_path(layer_name,project_name=self.project_name,
                                                project_folder=self.project_folder,
                                                style_folder=self.style_folder,
                                                parent=self,
                                                layout_mode=1)

                    if not layer_paths_dict:
                        messageLog(f"Layer NOT found: {layer_name}","w")
                        continue

                    layer_name_key = list(layer_paths_dict.keys())[0]
                    source_path = layer_paths_dict[layer_name_key]
                    final_path = source_path

                    # --------------------------------------------------
                    #  Vérifier si déjà chargé
                    # --------------------------------------------------

                    existing_layer = None
                    for l in self.project.mapLayers().values():
                        if l.source() == final_path:
                            existing_layer = l
                            break

                    if existing_layer:
                        node = root.findLayer(existing_layer.id())
                        if node and node.parent() != subgroup:
                            subgroup.addLayer(existing_layer)
                        continue


                    # --------------------------------------------------
                    #  Charger les couches sur QGIS
                    # --------------------------------------------------

                    loader(
                        {layer_name_key: final_path},
                        style_folder=self.style_folder,
                        project_folder=self.project_folder,
                        project_name=self.project_name,
                        group_name=canvas_group_name,
                        parent_group=subgroup,
                        parent=self)


    # ==========================================================
    # THEMES
    # ==========================================================
    def create_theme(self, name: str, visible_keys: list):
        """
        Crée un thème de carte QGIS à partir d'une liste de clés de layers.

        Args:
            name (str): Nom du thème.
            visible_keys (list): Liste de clés de couches visibles dans ce thème.

        Notes:
            - Les listes imbriquées sont aplaties automatiquement.
            - Les couches introuvables sont ignorées.
            - Écrase un thème existant si le même nom est utilisé.
        """

        # Aplatir visible_keys si nécessaire
        flat_keys = []
        for k in visible_keys:
            if isinstance(k, list):
                flat_keys.extend(k)
            else:
                flat_keys.append(k)


        resolved_layers = []

        for key in flat_keys:

            layer = resolve_layer(
                key,
                project=self.project,
                project_name=self.project_name,
                project_folder=self.project_folder,
                style_folder=self.style_folder,
                parent=None
            )

            # cas WMTS
            if not layer:
                display_name = self.config.get_wmts_display_name(key)

                if display_name:
                    layers = self.project.mapLayersByName(display_name)
                    layer = layers[0] if layers else None

            # fallback (préfixe projet)
            if not layer:
                for l in self.project.mapLayers().values():
                    if key.lower() in l.name().lower():
                        layer = l
                        break

            if layer:
                resolved_layers.append(layer)

        # Créer le MapThemeRecord
        mtc = self.project.mapThemeCollection()
        record = QgsMapThemeCollection.MapThemeRecord()

        for layer in resolved_layers:
            rec = QgsMapThemeCollection.MapThemeLayerRecord(layer)
            record.addLayerRecord(rec)

        # Insérer le thème (écrase automatiquement s'il existe)
        mtc = self.project.mapThemeCollection()
        mtc.insert(name, record)



    def create_all_themes(self):
        """
        Crée tous les thèmes définis dans la configuration YAML du projet.
        
        - Parcourt la liste des thèmes dans l'ordre inverse pour respecter la hiérarchie.
        - Utilise `create_theme` pour chaque thème.
        """

        for theme in reversed(self.canvas_cfg.themes):
            self.create_theme(theme.get("name"),theme.get("show", []))

    # ==========================================================
    # UI GROUP TREE
    # ==========================================================

    def fold_all(self):
        """
        Plie tous les groupes de l'arborescence de couches du projet.
        """

        root = self.project.layerTreeRoot()
        for node in root.children():
            node.setExpanded(False)

    def unfold(self, group_name):
        """
        Déplie un groupe spécifique dans l'arborescence de couches du projet.

        Args:
            group_name (str): Nom du groupe à déplier.
        """

        root = self.project.layerTreeRoot()
        group = root.findGroup(group_name)

        if group:
            group.setExpanded(True)

    # ==========================================================
    # ZOOM
    # ==========================================================

    def zoom_on_layer(self, key):
        """
        Zoome sur l'étendue de la couche spécifiée dans le canvas QGIS.

        Args:
            key (str): Clé de la couche à zoomer.
        """
        layer = resolve_layer(key,
                              project=self.project,
                              project_name=self.project_name,
                              project_folder=self.project_folder,
                              style_folder=self.style_folder,
                              parent=self)
        if not layer:
            return
        canvas = self.iface.mapCanvas()
        canvas.setExtent(layer.extent())
        canvas.refresh()


    # ==========================================================
    # OPACITY WMTS
    # ==========================================================

    def apply_scan25_opacity(self):
        """
        Applique une opacité de 50% à la couche WMTS 'scan25_grey' si elle existe.
        """

        layer_name = get_wmts("wmts_scan25_grey")[0]
        layers = self.project.mapLayersByName(layer_name)

        if layers:
            layers[0].setOpacity(0.5)

    # ==========================================================
    # MAIN BUILD METHOD
    # ==========================================================

    def build(self):
        """
        Méthode principale pour construire la mise en page du projet.

        Actions effectuées :
        1. Chargement des couches dans les groupes.
        2. Création de tous les thèmes.
        3. Pliage et dépliage de l'arborescence.
        4. Zoom sur la couche définie dans le YAML.
        5. Application de l'opacité sur la couche WMTS spécifique.
        6. Message de succès dans la barre d'état.
        """

        messageBar(self.iface, f"Création de la mise en page : {self.project_key}", "i",8)

        self.load_layer_and_groups() # Chargement des couches dans les groupes
        self.create_all_themes() # Chargement des 

        self.fold_all()
        self.unfold(self.project_key)

        self.zoom_on_layer(self.canvas_cfg.zoom_on)
        self.apply_scan25_opacity()

        messageBar(self.iface, f"Mise en page {self.project_key} chargé avec succès", "s",8)















