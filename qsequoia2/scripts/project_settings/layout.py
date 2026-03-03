import os


from qgis.core import (Qgis,QgsProject,QgsMessageLog,QgsLayerTreeGroup,QgsCoordinateReferenceSystem,QgsMapThemeCollection,)

from qgis.utils import iface

from ..utils.add_vector_layers import load_vectors
from ..utils.add_raster_layers import load_rasters
from ..utils.add_wmts_layers import load_wmts

from ..utils.layers import set_layers_readonly, resolve_layer
from ..utils.config import get_path, get_wmts
from .project_config import ProjectConfig
from ..utils.copy_to_gpkg import copy_to_gpkg
from ..utils.export_to_geojson import export_to_geojson



# ==========================================================
# PROJECT BUILDER CLASS
# ==========================================================

class ProjectBuilder:
    """
    Classe centralisée pour construire un projet QGIS
    à partir de project.yaml
    """


    def __init__(self,copy_layers,current_project_name,current_style_folder,downloads_path,current_project_folder,project_key: str,yaml_path: str,iface=None):

        self.copy_layers = copy_layers
        self.project_key = project_key
        self.iface = iface
        self.project = QgsProject.instance()
        self.parent = None

        # Variables projet
        self.project_name = current_project_name
        self.style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.project_folder = current_project_folder

        # Charger YAML
        self.config = ProjectConfig(yaml_path)

        self.canvas_cfg = self.config.get_project_canvas(project_key)
        self.layout_cfg = self.config.get_project_layout(project_key)
        print(self.project_folder)
        if not self.project_folder:
            raise ValueError("project_folder est None ! Tu dois passer un chemin valide.")


    # ==========================================================
    # LOGGING / MESSAGE
    # ==========================================================

    def message(self, text, level="info", duration=8):

        levels = {"info": Qgis.Info,"success": Qgis.Success,"warning": Qgis.Warning,"critical": Qgis.Critical,}

        qlevel = levels.get(level, Qgis.Info)

        try:
            self.iface.messageBar().pushMessage("Qsequoia2", text, level=qlevel, duration=duration)
        except Exception:
            print(text)

    # ==========================================================
    # CLEAR PROJECT 
    # ==========================================================

    #def clear(self, default_crs=2154):
        """supprime les couches et groupe du type de theme choisi uniquement"""

        #self.project.mapThemeCollection().clear()
        #self.project.layoutManager().clear()
        #self.project.layerTreeRoot().clear()
        #self.project.removeAllMapLayers()

        #self.project.setCrs(QgsCoordinateReferenceSystem.fromEpsgId(default_crs))

    # ==========================================================
    # THEMES
    # ==========================================================
    def create_theme(self, name: str, visible_keys: list):
        """
        Crée un thème de carte QGIS à partir de la liste de clés de layers.
        Cette version aplatit les listes imbriquées et ignore les layers introuvables.
        """

        # Aplatir visible_keys si nécessaire
        flat_keys = []
        for k in visible_keys:
            if isinstance(k, list):
                flat_keys.extend(k)
            else:
                flat_keys.append(k)

        # Résoudre les layers et garder les objets QgsMapLayer
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
            if layer:  # ignorer les None
                resolved_layers.append(layer)

        # Créer le MapThemeRecord
        mtc = self.project.mapThemeCollection()
        record = QgsMapThemeCollection.MapThemeRecord()

        for layer in resolved_layers:
            rec = QgsMapThemeCollection.MapThemeLayerRecord(layer)
            record.addLayerRecord(rec)

        # Insérer le thème
        mtc.insert(name, record)



    def create_all_themes(self):

        for theme in reversed(self.canvas_cfg.themes):
            self.create_theme(theme.get("name"),theme.get("show", []))

    # ==========================================================
    # LOAD GROUPS / LAYERS
    # ==========================================================


    def load_groups(self):

        print("=== LOAD GROUPS START ===")
        print("Canvas config groups:", self.canvas_cfg.groups)

        loaders = {
            "vector": load_vectors,
            "wmts": load_wmts,
            "raster": load_rasters,
        }

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
            if not loader:
                QgsMessageLog.logMessage(f"Groupe inconnu : {gtype}", "Qsequoia2", Qgis.Warning)
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

                    layer_paths_dict = get_path(
                        layer_name,
                        project_name=self.project_name,
                        project_folder=self.project_folder,
                        style_folder=self.style_folder,
                        parent=self,
                        layout_mode=1
                    )

                    if not layer_paths_dict:
                        print("Layer NOT found:", layer_name)
                        continue

                    layer_name_key = list(layer_paths_dict.keys())[0]
                    source_path = layer_paths_dict[layer_name_key]

                    # --------------------------------------------------
                    # Déterminer final_path
                    # --------------------------------------------------

                    if self.copy_layers:

                        vector_root = os.path.join(self.project_folder, "LAYOUT")
                        project_vector_dir = os.path.join(vector_root, self.project_key)
                        os.makedirs(project_vector_dir, exist_ok=True)

                        geojson_path = os.path.join(
                            project_vector_dir,
                            f"{self.project_key.upper()}_{layer_name_key}.geojson"
                        )

                        if not os.path.exists(geojson_path):
                            export_to_geojson(
                                layer_paths=[source_path],
                                project_vector_dir=project_vector_dir,
                                layer_name_override=layer_name_key
                            )

                        final_path = geojson_path

                    else:
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
                    #  Charger UNE SEULE FOIS
                    # --------------------------------------------------

                    loader(
                        {layer_name_key: final_path},
                        style_folder=self.style_folder,
                        project_folder=self.project_folder,
                        project_name=self.project_name,
                        group_name=canvas_group_name,
                        parent_group=subgroup,
                        parent=self
                    )

                    # TODO voir pour ajouter dans vecteurs les couches rajouté dans le LAYOUT de la compo


    # ==========================================================
    # READONLY
    # ==========================================================

    def apply_readonly(self):
        if self.canvas_cfg.readonly:
            set_layers_readonly(
                self.canvas_cfg.readonly,
                project=self.project,
                project_name=self.project_name,
                project_folder=self.project_folder,
                style_folder=self.style_folder,
                parent=self
            )


    # ==========================================================
    # UI GROUP TREE
    # ==========================================================

    def fold_all(self):

        root = self.project.layerTreeRoot()
        for node in root.children():
            node.setExpanded(False)

    def unfold(self, group_name):

        root = self.project.layerTreeRoot()
        group = root.findGroup(group_name)

        if group:
            group.setExpanded(True)

    # ==========================================================
    # ZOOM
    # ==========================================================

    def zoom_on_layer(self, key):
        layer = resolve_layer(
            key,
            project=self.project,
            project_name=self.project_name,
            project_folder=self.project_folder,
            style_folder=self.style_folder,
            parent=self
        )
        if not layer:
            return

        canvas = self.iface.mapCanvas()
        canvas.setExtent(layer.extent())
        canvas.refresh()


    # ==========================================================
    # OPACITY WMTS
    # ==========================================================

    def apply_scan25_opacity(self):

        layer_name = get_wmts("wmts_scan25_grey")[0]
        layers = self.project.mapLayersByName(layer_name)

        if layers:
            layers[0].setOpacity(0.5)

    # ==========================================================
    # MAIN BUILD METHOD
    # ==========================================================

    def build(self):

        self.message(f"Création du projet : {self.project_key}", "info")

        #self.clear()
        self.load_groups()
        self.apply_readonly()
        self.create_all_themes()

        self.fold_all()
        self.unfold("SEQUOIA")

        self.zoom_on_layer(self.canvas_cfg.zoom_on)
        self.apply_scan25_opacity()

        self.message("Projet chargé avec succès", "success")















