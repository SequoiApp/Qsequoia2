from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Optional, List

import os, datetime

from qgis.core import (
    QgsVectorLayer,
    QgsRectangle,
    QgsWkbTypes,
    QgsUnitTypes,
    QgsPrintLayout,
    QgsReadWriteContext,
    QgsLayoutItemMap,
    QgsLayoutFrame,
    QgsLayoutItemAttributeTable,
    QgsProject
)

from qgis.PyQt.QtXml import QDomDocument

from ..utils.variable import get_global_variable
from ..utils.config import get_path
from .processing import buffer, multipart_to_singleparts
from ..utils.layers import resolve_layer
from ..forest_settings.forest_stat import ForestStat


# ============================================================
# Data container
# ============================================================

@dataclass
class MapInfo:
    bbox: QgsRectangle
    orientation: str
    paper_format: str
    area: float


# ============================================================
#  Layout Service
# ============================================================

class LayoutService:
    """
    Service complet pour :

    - calculer le format papier optimal
    - importer un layout template QPT
    - configurer carte + thème + légendes
    - remplir automatiquement une table attributaire
    """

    FORMATS_MM: Tuple[Tuple[str, Tuple[int, int]], ...] = (
        ("A4", (210, 297)),
        ("A3", (297, 420)),
        ("A2", (420, 594)),
        ("A1", (594, 841)),
        ("A0", (841, 1189)),
    )

    # ------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------

    def __init__(self, project,project_key, project_name, style_folder, downloads_path, project_folder, iface):
        self.project = project
        self.iface = iface
        self.project_name = project_name
        self.style_folder = style_folder
        self.downloads_path = downloads_path
        self.project_folder = project_folder


        self.models_dir = Path(get_global_variable("models_directory"))

    # ============================================================
    # FORMAT + ORIENTATION
    # ============================================================

    def _fits_bbox(
        self,
        mm: Tuple[int, int],
        scale: int,
        bbox: QgsRectangle,
        coeff_cadre: float = 0.90,
        marge_mm: int = 6,
    ) -> bool:

        needed_w = (bbox.width() / scale) * 1000
        needed_h = (bbox.height() / scale) * 1000

        available_w = (mm[0] - 2 * marge_mm) * coeff_cadre
        available_h = (mm[1] - 2 * marge_mm) * coeff_cadre

        return needed_w <= available_w and needed_h <= available_h

    def _pick_format(self, scale: int, bbox: QgsRectangle, coeff=0.90) -> str:

        for name, mm in self.FORMATS_MM:
            if self._fits_bbox(mm, scale, bbox, coeff):
                return name

        return "A0+"

    def _pick_orientation(self, bbox: QgsRectangle) -> str:
        return "portrait" if bbox.height() >= bbox.width() else "landscape"

    # ============================================================
    # COMPUTE MAP INFO
    # ============================================================

    def compute_layout_info(
        self,
        uri: Optional[str] = None,
        scale: int = 15000,
        snap_distance: int = 200,
        coeff_cadre: float = 0.90,
        provider: str = "ogr",
    ) -> MapInfo:

        if uri is None:
            layer_dict = get_path("SEQ_PARCA_poly", project_name=self.project_name, project_folder=self.project_folder, style_folder=self.style_folder, parent=None)
        
        print("DEBUG: layer_dict =", layer_dict)
        if not layer_dict:
            raise ValueError(f"URI invalide : {uri}")
        uri = list(layer_dict.values())[0]
        print("DEBUG: layer URI =", uri)  # <-- URI finale


        layer = QgsVectorLayer(uri, "tmp", provider)
        print("DEBUG: layer isValid =", layer.isValid(), "featureCount =", layer.featureCount())  # <-- validité


        if not layer.isValid():
            raise ValueError(f"Layer invalide : {uri}")

        if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise TypeError("Layer doit être polygonal")

        if layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
            print("⚠ buffer interprété en unités CRS (pas mètres)")

        # --- PROCESS ---
        buffered = buffer(layer, distance=snap_distance / 2, dissolve=True)
        print("DEBUG: buffered featureCount =", buffered.featureCount() if buffered else None)  # <-- buffer

        dissolved = buffer(buffered, distance=-snap_distance / 2)
        print("DEBUG: dissolved featureCount =", dissolved.featureCount() if dissolved else None)  # <-- dissolve

        single_parts = multipart_to_singleparts(dissolved)
        print("DEBUG: single_parts featureCount =", single_parts.featureCount())  # <-- single parts

        feat = max(
            single_parts.getFeatures(),
            key=lambda f: f.geometry().area(),
            default=None,
        )

        if feat is None or feat.geometry().isEmpty():
            raise ValueError("Aucune géométrie valide trouvée")

        geom = feat.geometry()
        bbox = geom.boundingBox()
        print("DEBUG: bbox =", bbox.toString(), "width/height =", bbox.width(), bbox.height())


        fmt = self._pick_format(scale, bbox, coeff_cadre)
        orient = self._pick_orientation(bbox)
        print("DEBUG: picked format =", fmt, "orientation =", orient)


        return MapInfo(
            bbox=bbox,
            orientation=orient,
            paper_format=fmt,
            area=geom.area(),
        )



    # ============================================================
    # TEMPLATE IMPORT
    # ============================================================

    def _find_template(self, fmt: str, orient: str):

        orient = orient.lower().strip()

        qpt = self.models_dir / f"{fmt}_{orient}.qpt"
        if qpt.exists():
            return qpt, orient

        # fallback orientation
        other = "portrait" if orient == "landscape" else "landscape"
        qpt = self.models_dir / f"{fmt}_{other}.qpt"

        if qpt.exists():
            return qpt, other

        base = Path(__file__).resolve()
        QS_templates = base.parents[2] / "data" / "templates"

        qpt = QS_templates / f"{fmt}_{orient}.qpt"
        if qpt.exists():
            return qpt, orient

        qpt_other = QS_templates / f"{fmt}_{other}.qpt"
        if qpt_other.exists():
            return qpt_other, other


        raise FileNotFoundError(f"Template introuvable : {fmt}_{orient}")

    def import_layout(self, project_key, fmt: str, orient: str) -> QgsPrintLayout:

        qpt, orient_used = self._find_template(fmt, orient)

        layout = QgsPrintLayout(self.project)
        layout.initializeDefaults()

        doc = QDomDocument()
        xml = qpt.read_text(encoding="utf-8")

        if not doc.setContent(xml):
            raise ValueError("QPT invalide")

        layout.loadFromTemplate(doc, QgsReadWriteContext())
        #try :
        # Nom de la carte courante 
        # import de forest_stat pour les département
        forest_stats = ForestStat(project=QgsProject.instance(),project_name=self.project_name,project_folder=self.project_folder,style_folder=self.style_folder,iface=self.iface)
        departements = forest_stats.forest_departements(layers = 'SEQ_PARCA_poly',project_name=self.project_name,project_folder=self.project_folder,style_folder=self.style_folder)
        # Année courante
        years = datetime.datetime.now().year

        # build des noms

        deps = str(departements.replace(" ","").replace("&","-").replace(",","-"))
        layout.setName(f"{deps}-{self.project_name.upper()}-{project_key}-{years}_{fmt}_{orient_used}")

        #self.project.layoutManager().addLayout(layout)

        return layout

    # ============================================================
    # CONFIGURE LAYOUT
    # ============================================================

    def configure_layout(
        self,
        layout: QgsPrintLayout,
        theme: str = None,
        scale: int = None,
        legends: list = None,
        hide_legend_names: bool = False,):

        # --- MAP ITEM ---
        maps = [i for i in layout.items() if isinstance(i, QgsLayoutItemMap)]
        if not maps:
            raise ValueError("Aucune carte trouvée")

        map_item = next((m for m in maps if m.id() == "map1"), maps[0])

        # Zoom extent
        map_item.zoomToExtent(self.iface.mapCanvas().extent())

        # Theme
        if theme:
            themes = self.project.mapThemeCollection().mapThemes()
            if theme not in themes:
                raise ValueError(f"Thème '{theme}' introuvable")

            map_item.setFollowVisibilityPreset(True)
            map_item.setFollowVisibilityPresetName(theme)

        # Scale
        if scale:
            map_item.setScale(scale)

        # Legends
        if legends:
            for l in legends:
                self.add_layer_to_legend(
                    layout=layout,
                    legend_id=l["name"],
                    layer_keys=l["layers"],
                    hide_name=hide_legend_names,
                    map_id="map1",
                )

        # ====================================================
        # AUTO TABLE CONFIG
        # ====================================================

        path = get_path("SEQ_PF_poly", project_name= self.project_name, project_folder=self.project_folder, style_folder = self.style_folder, parent=None)

        if path:
            first_key = list(path.keys())[0]
            path = path[first_key]
            layer_name = Path(path).stem
            layers = self.project.mapLayersByName(layer_name)

            if layers:
                self.configure_attribute_table(
                    layout=layout,
                    table_id="table1",
                    layer_key=layer_name,
                    fields=["N_PARFOR", "SURF_COR"],
                    map_id="map1",
                    filter_expression='"N_PARFOR" <> \'00\'',
                )

    # ============================================================
    # LEGEND
    # ============================================================

    def add_layer_to_legend(
        self,
        layout,
        legend_id: str,
        layer_keys: list,
        hide_name: bool = True,
        map_id: str = None,
    ):


        legend = layout.itemById(legend_id)
        if not legend:
            raise ValueError(f"Légende '{legend_id}' introuvable")

        root = legend.model().rootGroup()

        for key in layer_keys:

            layer = resolve_layer(key, self.project, project_name=self.project_name, project_folder=self.project_folder, style_folder=self.style_folder, parent=None)

            if not layer:
                continue   # ne stoppe pas tout

            # éviter doublon
            if layer.id() in [n.layerId() for n in root.findLayers()]:
                continue

            node = root.addLayer(layer)

            if hide_name:
                node.setName("")

        # Filtrage map
        if map_id:
            map_item = layout.itemById(map_id)
            legend.setLinkedMap(map_item)
            legend.setLegendFilterByMapEnabled(True)

        legend.refresh()

    # ============================================================
    # ATTRIBUTE TABLE
    # ============================================================
    def configure_attribute_table(
        self,
        layout,
        table_id: str,
        layer_key: str,
        fields: list,
        map_id: str = None,
        filter_expression: str = None,
    ):

        item = layout.itemById(table_id)
        if not item:
            raise ValueError(f"Table '{table_id}' introuvable")

        # MultiFrame support
        if isinstance(item, QgsLayoutFrame):
            table = item.multiFrame()
        else:
            table = item

        # Résolution propre via resolve_layer
        layer = resolve_layer(layer_key,
                                project=self.project,
                                project_name=self.project_name,
                                project_folder=self.project_folder,
                                style_folder=self.style_folder,
                                parent=None)


        if not layer:
            raise ValueError(f"Couche '{layer_key}' introuvable ou non chargée")

        # Appliquer couche + champs
        table.setVectorLayer(layer)
        table.setDisplayedFields(fields)

        # Visible only
        if map_id:
            map_item = layout.itemById(map_id)
            if map_item:
                table.setMap(map_item)
                table.setDisplayOnlyVisibleFeatures(True)

        # Filtre
        if filter_expression:
            table.setFeatureFilter(filter_expression)
            table.setFilterFeatures(True)

        table.refresh()
