from pathlib import Path
from qgis.core import (QgsProject,QgsVectorLayer,QgsMessageLog,Qgis,QgsRelation,QgsEditorWidgetSetup,)
from osgeo import ogr

from .config import get_wmts, get_display_name



def resolve_layer_name(key: str) -> str:
    # Try alias lookup
    try:
        name = get_display_name(key)   # vector/alias
        if name:
            return name
    except KeyError:
        pass

    # Try WMTS lookup
    try:
        layer_name, _ = get_wmts(key)   # WMTS fallback
        if layer_name:
            return layer_name
    except KeyError:
        pass

    # Final fallback: assume it's already a layer name
    return key
   

def set_layers_readonly(*keys):
    for key in keys:
        name = get_display_name(key)
        layer = QgsProject.instance().mapLayersByName(name)
        if layer:
            vector_layer = layer[0]
            if isinstance(vector_layer, QgsVectorLayer):
                vector_layer.setReadOnly(True)

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
