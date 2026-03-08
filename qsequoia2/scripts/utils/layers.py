# ==================================================================================
# Import
# ==================================================================================

# Python
from pathlib import Path

# QGIS
from qgis.core import (QgsProject,QgsMessageLog,Qgis)
from osgeo import ogr

# QSEQUOIA2

from .config import get_path

# ==================================================================================
# resolve layer
# ==================================================================================

def resolve_layer(layer_key: str,project=None,project_name=None,project_folder=None,style_folder=None,parent=None):
    """
    Résout et retourne une couche QGIS à partir d'une clé logique.

    Cette fonction utilise la clé de couche pour retrouver son chemin via
    la fonction ``get_path`` puis recherche la couche correspondante déjà
    chargée dans le projet QGIS.
    """

    if project is None:
        project = QgsProject.instance()

    # get_path retourne un dict {layer_key: path}
    layer_paths_dict = get_path(layer_key,project_name=project_name,
                                project_folder=project_folder,style_folder=style_folder,parent=parent)

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

# ==================================================================================
# set_layers_readonly
# ==================================================================================

def set_layers_readonly(layer_keys,project=None,project_name=None,project_folder=None,style_folder=None,parent=None):
    """
    Passe une ou plusieurs couches en mode lecture seule dans le projet QGIS.

    Les couches sont identifiées à partir de leurs clés logiques, puis
    résolues via ``resolve_layer``.
    """

    if project is None:
        project = QgsProject.instance()

    if isinstance(layer_keys, str):
        layer_keys = [layer_keys]

    for key in layer_keys:
        layer = resolve_layer(key,project=project,project_name=project_name,project_folder=project_folder,
                              style_folder=style_folder,parent=parent)
        
        if not layer:
            continue
        layer.setReadOnly(True)


# ==================================================================================
# configure_snapping
# ==================================================================================

def configure_snapping():
    """
    Configure les paramètres globaux d'accrochage (snapping) du projet QGIS.

    La configuration appliquée inclut :
    - activation globale du snapping,
    - accrochage sur toutes les couches du projet,
    - accrochage sur sommets, segments, milieux et extrémités,
    - tolérance de 15 pixels,
    - détection des intersections,
    - activation de l'édition topologique.

    Cette configuration est appliquée directement au projet courant.

    :return: None
    """

    project = QgsProject.instance()
    cfg = project.snappingConfig()       # référence vers la config actuelle

    # Activation globale
    cfg.setEnabled(True)

    # Accrochage sur toutes les couches
    cfg.setMode(Qgis.SnappingMode.AllLayers)

    # Types d’accrochage
    cfg.setTypeFlag(Qgis.SnappingTypes(Qgis.SnappingType.Vertex | Qgis.SnappingType.Segment |
                           Qgis.SnappingType.MiddleOfSegment |Qgis.SnappingType.LineEndpoint))

    # Tolérance & unités
    cfg.setTolerance(15)                         # 15 px
    cfg.setUnits(Qgis.MapToolUnit.Pixels)

    # Snapping divers
    cfg.setIntersectionSnapping(True)            # attraper les intersections
    cfg.setSelfSnapping(False)                   # pas de self-snapping (≥ 3.14)

    # Options de topologie & chevauchement
    project.setTopologicalEditing(True)
    project.setAvoidIntersectionsMode(Qgis.AvoidIntersectionsMode.AllowIntersections)

    # On pousse la config et on rafraîchit éventuellement le canevas
    project.setSnappingConfig(cfg)                                  

    return None
