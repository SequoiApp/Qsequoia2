# ==================================================================================
# Import
# ==================================================================================

from qgis.core import (QgsProject,Qgis)

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
