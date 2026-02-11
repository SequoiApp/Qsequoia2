from qgis.core import (Qgis,QgsProject,QgsMessageLog,QgsLayerTreeGroup,QgsCoordinateReferenceSystem,QgsMapThemeCollection,)

from qgis.utils import iface

from ..utils.add_vector_layers import load_vectors
from ..utils.add_raster_layers import load_rasters
from ..utils.add_wmts_layers import load_wmts

from ..utils.layers import set_layers_readonly, resolve_layer_name
from ..utils.config import get_display_name, get_path, get_wmts
from .project_config import ProjectConfig
from ..utils.copy_to_gpkg import copy_to_gpkg



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

    def clear(self, default_crs=2154):

        self.project.mapThemeCollection().clear()
        self.project.layoutManager().clear()
        self.project.layerTreeRoot().clear()
        self.project.removeAllMapLayers()

        self.project.setCrs(QgsCoordinateReferenceSystem.fromEpsgId(default_crs))

    # ==========================================================
    # THEMES
    # ==========================================================

    def create_theme(self, name: str, visible_keys: list[str]):

        resolved_names = {resolve_layer_name(k) for k in visible_keys}

        mtc = self.project.mapThemeCollection()
        record = QgsMapThemeCollection.MapThemeRecord()

        # map name → layer
        name_to_layer = {
            layer.name(): layer
            for layer in self.project.mapLayers().values()}

        for layer_name in resolved_names:
            layer = name_to_layer.get(layer_name)
            if layer:
                rec = QgsMapThemeCollection.MapThemeLayerRecord(layer)
                record.addLayerRecord(rec)

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

        for group in self.canvas_cfg.groups:

            gtype = group.get("type")
            layers = group.get("layers") or []
            group_name = group.get("name", "Sans nom")

            loader = loaders.get(gtype)

            if not loader:
                QgsMessageLog.logMessage(
                    f"Groupe inconnu : {gtype}",
                    "Qsequoia2",
                    Qgis.Warning
                )
                continue

            # ======================================================
            # WMTS : appeler une seule fois avec la liste
            # ======================================================
            if gtype == "wmts":
                loader(layers,group_name=group_name)
                continue
            # ======================================================
            # VECTOR / RASTER : boucle couche par couche
            # ======================================================
            if self.copy_layers == True:

                for layer_name in layers:
                    layer_paths = get_path(layer_name, project_name=self.project_name, project_folder=self.project_folder, style_folder=self.style_folder, parent=self)
                    if layer_paths:
                        layer_paths = list(layer_paths.values())[0]
                        print("DEBUG final layer_paths =", layer_paths)
                        copy_to_gpkg(self.project_key,layer_paths, self.style_folder, self.project_folder, self.project_name, group_name, parent=None)
            else :
            # Sinon on les charges depuis leur chemin d'origine (utile pour le dev)
                for layer_name in layers:

                    layer_paths = get_path(layer_name, project_name=self.project_name, project_folder=self.project_folder, style_folder=self.style_folder, parent=self)
                    if layer_paths:
                        loader(layer_paths, style_folder=self.style_folder, project_folder=self.project_folder, project_name=self.project_name, group_name=group_name, parent=self)
                    else:
                        print("Layer NOT found:", layer_name)


    # ==========================================================
    # READONLY
    # ==========================================================

    def apply_readonly(self):

        if self.canvas_cfg.readonly:
            set_layers_readonly(*self.canvas_cfg.readonly)

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

        layers = self.project.mapLayersByName(get_display_name(key))
        if not layers:
            return

        layer = layers[0]
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

        self.clear()
        self.load_groups()
        self.apply_readonly()
        self.create_all_themes()

        self.fold_all()
        self.unfold("SEQUOIA")

        self.zoom_on_layer(self.canvas_cfg.zoom_on)
        self.apply_scan25_opacity()

        self.message("Projet chargé avec succès", "success")
