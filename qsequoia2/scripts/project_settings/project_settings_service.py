from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from qgis.core import QgsVectorLayer, QgsRectangle, QgsWkbTypes, QgsUnitTypes, QgsPrintLayout, QgsReadWriteContext, QgsLayoutItemMap, QgsLayoutFrame, QgsLayoutItemAttributeTable
from qgis.PyQt.QtXml import QDomDocument

from ..utils.variable import get_global_variable
from .processing import buffer, multipart_to_singleparts
from ..utils.config import get_display_name, get_path

# region LAYOUT CREATION
@dataclass
class MapInfo:
    bbox: QgsRectangle
    orientation: str          # 'portrait' | 'landscape'
    paper_format: str         # 'A4', 'A3', …, 'A0+'
    area: float

FORMATS_MM: Tuple[Tuple[str, Tuple[int, int]], ...] = (
    ("A4", (210, 297)),
    ("A3", (297, 420)),
    ("A2", (420, 594)),
    ("A1", (594, 841)),
    ("A0", (841, 1189)),
)

def _fits_bbox(
        mm: Tuple[float, float],
        scale: int,
        bbox: QgsRectangle,
        coeff_cadre=0.90,
        marge_mm=6) -> bool:
    """
    True if the paper size `mm` (in millimetres) at `scale` can contain
    the given map extent `bbox` (in map units) in *either* orientation.
    """
    # Required paper dimensions in mm at this scale
    needed_w, needed_h = ((bbox.width() / scale) * 1000.0, (bbox.height() / scale) * 1000.0)
    available_w, available_h = ((d - 2 * marge_mm) * coeff_cadre for d in mm)

    return needed_w <= available_w and needed_h <= available_h

def _pick_format(scale: int, bbox: QgsRectangle, coeff_cadre = 0.90) -> str:
    """
    Return the smallest paper format that fits the given `bbox` at `scale`.
    If none fit, return 'A0+'.
    """
    for name, mm in FORMATS_MM:
        if _fits_bbox(mm, scale, bbox, coeff_cadre):
            return name
    return "A0+"

def _pick_orient(bbox: QgsRectangle) -> str:
    return "portrait" if bbox.height() >= bbox.width() else "landscape"

def compute_layout_info(
        uri = None,
        scale: int = 15000,
        snap_distance : int = 200,
        coeff_cadre = 0.90,
        provider: str = "ogr") -> MapInfo:

    if uri is None:
        uri = str(get_path("parca_polygon"))

    info_layer = QgsVectorLayer(uri, "tmp", provider)
    if not info_layer.isValid():
        raise ValueError(f"Invalid layer URI: {uri}")
    if QgsWkbTypes.geometryType(info_layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
        raise TypeError("Layer must be polygonal.")
    
    if info_layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
        print("Warning: buffer_distance is interpreted in layer CRS units, not meters.")
    
    # Process
    # 1 : buffer each part to profit of dissolve arg
    # 2 : unbuffer to have real size of the forest
    buffered_and_dissolve = buffer(info_layer, distance=snap_distance/2, dissolve=True)
    dissolved = buffer(buffered_and_dissolve, distance=-snap_distance/2)
    single_parts_layer = multipart_to_singleparts(dissolved)

    # Safe max with default
    feat = max(single_parts_layer.getFeatures(), key=lambda f: f.geometry().area(), default=None)
    if feat is None or feat.geometry() is None or feat.geometry().isEmpty():
        raise ValueError("No valid geometry found after buffering/splitting.")

    geom = feat.geometry()
    bbox = geom.boundingBox()

    fmt = _pick_format(scale, bbox, coeff_cadre)
    orient = _pick_orient(bbox)

    return MapInfo(bbox=bbox, orientation=orient, paper_format=fmt, area=geom.area())

def _find_template(models_dir, fmt, orient):
    """
    Look for {fmt}_{orient}.qpt; if not found, try the opposite orientation.
    Returns the found path and orientation used.
    Raises FileNotFoundError if neither exists.
    """
    # Normalize to lower case for file naming
    fmt = fmt.strip()
    orient = orient.strip().lower()  # type: ignore

    # 1) Exact orientation
    qpt = models_dir / f"{fmt}_{orient}.qpt"
    if qpt.exists():
        return qpt, orient  # found exact

    # 2) Else try the other orientation
    orient = "portrait" if orient == "landscape" else "landscape"
    qpt = models_dir / f"{fmt}_{orient}.qpt"
    if qpt.exists():
        return qpt, orient

    # 3) Nothing found
    raise FileNotFoundError(
        f"Template introuvable : {fmt}_{orient}.qpt ni {fmt}_{orient}.qpt"
    )

def import_layout(project, fmt: str, orient):
    models_dir = Path(get_global_variable('models_directory'))
    qpt, orient = _find_template(models_dir, fmt, orient)
    
    manager = project.layoutManager()
    layout_name = f"{fmt}_{orient}"

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()

    # Read & parse XML
    doc = QDomDocument()
    with open(qpt, "r", encoding="utf-8") as fh:
        xml = fh.read()
    if not doc.setContent(xml):
        raise ValueError(f"QPT invalide (XML): {qpt}")

    # Load template and register
    layout.loadFromTemplate(doc, QgsReadWriteContext())
    layout.setName(layout_name)
    manager.addLayout(layout)
    return layout
  
# endregion

# region LAYOUT CONFIGURATION
def configure_layout(
        project,
        iface,
        layout: QgsPrintLayout,
        theme: str,
        scale: str,
        legends: list = None,
        hide_legend_names: bool = False
        ) -> None:

    # Récupérer toutes les cartes dans le layout
    all_maps = [item for item in layout.items() if isinstance(item, QgsLayoutItemMap)]
    if not all_maps:
        raise ValueError("Aucune carte (QgsLayoutItemMap) trouvée dans le layout.")

    # Zoom sur l'emprise actuelle du canevas
    for map_item in all_maps:
        map_item.zoomToExtent(iface.mapCanvas().extent())

    # On privilégie la carte "map1" si elle existe
    map_item = next((m for m in all_maps if m.displayName() == "map1"), all_maps[0])

    # Appliquer un thème de carte si défini
    if theme:
        theme_collection = project.mapThemeCollection()
        if theme not in theme_collection.mapThemes():
            raise ValueError(f"Le thème de carte '{theme}' est introuvable dans le projet.")

        map_item.setFollowVisibilityPreset(True)
        map_item.setFollowVisibilityPresetName(theme)

    # Appliquer une échelle fixe si définie
    if scale:
        map_item.setScale(scale)

    # Ajouter la légende si spécifiée
    for l in legends:
        legend_name = l.get("name")
        legend_layers = l.get("layers")
        add_layer_to_legend(project, layout, legend_name, *legend_layers, hide_name=hide_legend_names)

    # Complète la table
    pf_display_name = get_display_name("pf_polygon")
    layers = project.mapLayersByName(pf_display_name)
    if layers:
      configure_attribute_table(
          project,
          layout,
          table_id = "table1",
          layer_key = "pf_polygon",
          fields = ["N_PARFOR", "SURF_COR"],
          map_id = "map1",
          filter_expression = '"N_PARFOR" <> \'00\''
        )
        
def add_layer_to_legend(
        project,
        layout: QgsPrintLayout,
        legend_id: str, 
        *layer_keys: list, 
        hide_name: bool = True, 
        map_id: str = None
        ):
    """
    Ajoute des couches à une légende dans un composeur, avec option de filtrage par contenu visible sur une carte.

    :param layout: QgsPrintLayout
    :param legend_id: ID de l'objet légende dans le composeur
    :param layer_keys: liste de clés logiques de couches à ajouter
    :param hide_name: masque le nom de la couche dans la légende
    :param map_id: ID de l'objet carte (QgsLayoutItemMap) pour filtrer par contenu visible
    """
    legend = layout.itemById(legend_id)
    if not legend:
        raise ValueError(f"Élément légende '{legend_id}' non trouvé")

    root = legend.model().rootGroup()

    for key in layer_keys:
        display_name = get_display_name(key)
        layers = project.mapLayersByName(display_name)
        if layers:
            layer = layers[0]
            existing_layers = [node.layerId() for node in root.findLayers()]
            if layer.id() in existing_layers:
                print(f"La couche '{display_name}' est déjà dans la légende")
                continue
            legend_node = root.addLayer(layer)
            if hide_name:
                legend_node.setName("")

    # Lier la légende à une carte spécifique pour filtrer les entités visibles
    if map_id:
        map_item = layout.itemById(map_id)
        if not isinstance(map_item, QgsLayoutItemMap):
            raise TypeError(f"L'élément '{map_id}' n'est pas une carte (QgsLayoutItemMap)")
        legend.setLinkedMap(map_item)
        legend.setLegendFilterByMapEnabled(True)

    legend.refresh()

def configure_attribute_table(
        project,
        layout: QgsPrintLayout, 
        table_id: str, 
        layer_key: str, 
        fields: list,
        map_id: str = None,
        filter_expression: str = None):
    """
    Configure une table attributaire dans un layout QGIS 3.40.

    :param layout: QgsPrintLayout contenant la table
    :param table_id: ID de la table dans le composeur
    :param layer_key: clé logique de la couche (convertie avec get_display_name)
    :param fields: liste de champs à afficher
    :param show: ne montrer que les entités visibles
    :param filter_expression: expression QGIS pour filtrer les entités (ex: '"N_PARFOR" <> \'00\'')
    :param alignments: dict facultatif pour aligner les colonnes, ex: {'N_PARFOR': Qt.AlignCenter}
    """
    item = layout.itemById(table_id)
    if not item:
        raise ValueError(f"Élément table '{table_id}' non trouvé dans le layout.")

    if isinstance(item, QgsLayoutFrame):
        table = item.multiFrame()
    elif isinstance(item, QgsLayoutItemAttributeTable):
        table = item
    else:
        raise TypeError(f"L'élément '{table_id}' n'est ni une table ni une frame de table.")

    display_name = get_display_name(layer_key)
    layers = project.mapLayersByName(display_name)
    if not layers:
        raise ValueError(f"Aucune couche trouvée avec le nom '{display_name}'")
    layer = layers[0]

    table.setVectorLayer(layer)
    table.setDisplayedFields(fields)
    
    # setDisplayOnlyVisibleFeatures
    if map_id:
      map_item = layout.itemById(map_id)
      if map_item:
        table.setMap(map_item)
        table.setDisplayOnlyVisibleFeatures(True)
    
    # Appliquer le filtre si fourni
    if filter_expression:
        table.setFeatureFilter(filter_expression)
        table.setFilterFeatures(True)

    table.refresh()

# endregion