from pathlib import Path
from qgis.core import (QgsProject,QgsVectorLayer,QgsMessageLog,Qgis,QgsRelation,QgsEditorWidgetSetup,)
from osgeo import ogr

from .config import get_path, get_wmts

def resolve_layer(
    layer_key: str,
    project=None,
    project_name=None,
    project_folder=None,
    style_folder=None,
    parent=None
):
    if project is None:
        project = QgsProject.instance()

    # get_path retourne un dict {layer_key: path}
    layer_paths_dict = get_path(
        layer_key,
        project_name=project_name,
        project_folder=project_folder,
        style_folder=style_folder,
        parent=parent
    )

    if not layer_paths_dict:
        QgsMessageLog.logMessage(f"Couche '{layer_key}' introuvable", level=Qgis.Warning)
        return None

    # Extraire le chemin réel depuis le dict
    path = next(iter(layer_paths_dict.values()))
    if not path:
        QgsMessageLog.logMessage(f"Couche '{layer_key}' introuvable", level=Qgis.Warning)
        return None

    filename = Path(path).stem
    layers = project.mapLayersByName(filename)
    return layers[0] if layers else None

def set_layers_readonly(
    layer_keys,
    project=None,
    project_name=None,
    project_folder=None,
    style_folder=None,
    parent=None
):
    if project is None:
        project = QgsProject.instance()

    if isinstance(layer_keys, str):
        layer_keys = [layer_keys]

    for key in layer_keys:
        layer = resolve_layer(
            key,
            project=project,
            project_name=project_name,
            project_folder=project_folder,
            style_folder=style_folder,
            parent=parent
        )
        if not layer:
            continue
        layer.setReadOnly(True)





def configure_snapping():
    project = QgsProject.instance()
    cfg = project.snappingConfig()       # référence vers la config actuelle

    # 1. Activation globale
    cfg.setEnabled(True)

    # 2. Accrochage sur toutes les couches
    cfg.setMode(Qgis.SnappingMode.AllLayers)

    # 3. Types d’accrochage
    cfg.setTypeFlag(
        Qgis.SnappingTypes(
            Qgis.SnappingType.Vertex |
            Qgis.SnappingType.Segment |
            Qgis.SnappingType.MiddleOfSegment |
            Qgis.SnappingType.LineEndpoint
        )
    )

    # 4. Tolérance & unités
    cfg.setTolerance(15)                         # 15 px
    cfg.setUnits(Qgis.MapToolUnit.Pixels)

    # 5. Snapping divers
    cfg.setIntersectionSnapping(True)            # attraper les intersections
    cfg.setSelfSnapping(False)                   # pas de self-snapping (≥ 3.14)

    # 6. Options de topologie & chevauchement
    project.setTopologicalEditing(True)
    project.setAvoidIntersectionsMode(
        Qgis.AvoidIntersectionsMode.AllowIntersections
    )

    # 7. On pousse la config et on rafraîchit éventuellement le canevas
    project.setSnappingConfig(cfg)                                  

    return None
