from pathlib import Path

from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    QgsLayoutFrame,
    QgsLayoutItemMap,
    QgsPrintLayout,
    QgsReadWriteContext,
    QgsRectangle,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
)

from ..utils.messageBar import messageBar, messageLog
from ..utils.variable import get_global_variable, get_project_variable
from ..utils.seq_config import seq_field, seq_read
from .processing import buffer, multipart_to_singleparts

TEMPLATE_DIR = Path(__file__).parents[2] / "data" / "templates"


class LayoutBuilder:
    FORMATS_MM = (
        ("A4", (210, 297)),
        ("A3", (297, 420)),
        ("A2", (420, 594)),
        ("A1", (594, 841)),
        ("A0", (841, 1189)),
    )

    def __init__(self, iface, project, seq_id, layout_cfg, layers, coeff_cadre: float = 0.90):
        self.iface = iface
        self.project = project
        self.seq_id = seq_id
        self.layout = layout_cfg
        self.key = self.layout.key
        self.layers = layers
        self.coeff_cadre = coeff_cadre

    def build(self):
        project_folder = get_project_variable("QS2_seq_dir") or None
        parca = seq_read("parca", add_to_project=False, project_folder=project_folder)
        if not parca:
            raise RuntimeError("[LAYOUT] Couche 'parca' absente du contexte")

        fmt, orient = self._compute_layout_info(parca)
        layout = self._create_layout(fmt, orient)

        self._set_visibility()
        self._configure_maps(layout)
        self._configure_legends(layout)
        self._add_parcels_table(layout)

        messageLog(f"Layout '{layout.name()}' configuré avec succès")
        return layout

    def _layer(self, key):
        return self.layers.get(key)

    def _compute_layout_info(self, parca: QgsVectorLayer):
        if not parca or not parca.isValid():
            raise ValueError("[parca] Couche invalide ou non chargée")

        if QgsWkbTypes.geometryType(parca.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise TypeError("[parca] La couche doit être polygonale")

        if parca.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
            raise TypeError("[parca] CRS non métrique")

        geom = self._get_main_massif(parca)
        if geom is None or geom.isEmpty():
            raise ValueError("[parca] Géométrie principale vide")

        bbox = geom.boundingBox()
        fmt = self._pick_format(bbox)
        orient = self._pick_orient(bbox)

        return fmt, orient

    def _get_main_massif(self, layer: QgsVectorLayer):
        buffered = buffer(layer, distance=100, dissolve=True)
        dissolved = buffer(buffered, distance=-100)
        single_parts = multipart_to_singleparts(dissolved)

        feat = max(
            single_parts.getFeatures(),
            key=lambda f: f.geometry().area(),
            default=None,
        )

        if not feat or feat.geometry().isEmpty():
            raise ValueError("No valid geometry found")

        return feat.geometry()

    def _pick_format(self, bbox: QgsRectangle) -> str:
        scale = self.layout.main_scale
        if scale is None:
            raise ValueError("[LAYOUT] layout.scale est requis pour calculer le format")

        for name, mm in self.FORMATS_MM:
            if self._fits_bbox(mm, bbox, scale):
                return name
        return "A0+"

    def _fits_bbox(self, mm, bbox, scale, marge_mm=6):
        needed_w = (bbox.width() / scale) * 1000.0
        needed_h = (bbox.height() / scale) * 1000.0

        available_w = (mm[0] - 2 * marge_mm) * self.coeff_cadre
        available_h = (mm[1] - 2 * marge_mm) * self.coeff_cadre

        return needed_w <= available_w and needed_h <= available_h

    @staticmethod
    def _pick_orient(bbox):
        return "portrait" if bbox.height() >= bbox.width() else "landscape"

    def _create_layout(self, fmt: str, orient: str) -> QgsPrintLayout:
        lm = self.project.layoutManager()

        qpt, final_orient = self._find_template(
            [
                Path(get_global_variable("QS2_models_directory") or ""),
                TEMPLATE_DIR,
            ],
            fmt,
            orient,
        )

        messageLog(f"[TEMPLATE] Template trouvé: {qpt} (format={fmt}, orient={final_orient})")

        layout_name = f"{self.seq_id}_{self.key}_{fmt}_{final_orient}"

        existing = lm.layoutByName(layout_name)
        if existing:
            return existing

        layout = QgsPrintLayout(self.project)
        layout.initializeDefaults()

        doc = QDomDocument()
        with open(qpt, encoding="utf-8") as f:
            if not doc.setContent(f.read()):
                raise ValueError(f"[Lecture QPT] XML invalide : {qpt}")

        layout.loadFromTemplate(doc, QgsReadWriteContext())
        layout.setName(layout_name)

        lm.addLayout(layout)
        return layout

    def _find_template(self, models_dirs, fmt, orient):
        orient = orient.lower()
        tried = []

        for models_dir in models_dirs:
            if not models_dir.exists():
                tried.append(f"{models_dir} (absent)")
                continue

            for o in (orient, "portrait" if orient == "landscape" else "landscape"):
                qpt = models_dir / f"{fmt}_{o}.qpt"
                tried.append(str(qpt))

                if qpt.exists():
                    return qpt, o

        raise FileNotFoundError(
            f"Aucun template trouvé pour '{fmt}' ({orient}).\n"
            f"Recherché dans :\n- " + "\n- ".join(tried)
        )

    def _get_map_item(self, layout, map_id: str) -> QgsLayoutItemMap:
        item = layout.itemById(map_id)
        messageLog(f"[LAYOUT] Recherche de l'item '{map_id}'")

        if not item:
            raise messageLog(f"[Layout] Carte '{map_id}' introuvable")

        if not isinstance(item, QgsLayoutItemMap):
            raise messageLog(f"[Layout] L'item '{map_id}' n'est pas une carte")

        return item

    def _resolve_map_layers(self, map_spec):
        map_layers = []

        for key in map_spec.layers:
            layer = self._layer(key)
            if not layer:
                messageLog(f"[LAYOUT] couche absente du contexte: {key}")
                continue
            map_layers.append(layer)

        if not map_layers:
            raise ValueError(f"[Layout] Aucune couche valide pour la carte '{map_spec.id}'")

        return map_layers

    def _configure_maps(self, layout):
        canvas = self.iface.mapCanvas()

        for map_spec in self.layout.maps:
            map_item = self._get_map_item(layout, map_spec.id)
            messageLog(f"[LAYOUT] configuring: {map_spec.id} with layers: {map_spec.layers} (main_map={map_spec.main_map})")

            if map_spec.main_map:
                map_item.setKeepLayerSet(False)
                map_item.setFollowVisibilityPreset(False)
                map_item.zoomToExtent(canvas.extent())

            else:
                map_layers = self._resolve_map_layers(map_spec)

                map_item.setKeepLayerSet(True)
                map_item.setFollowVisibilityPreset(False)
                map_item.setLayers(map_layers)

                map_item.zoomToExtent(canvas.extent())

            # scale (common logic)
            scale = map_spec.scale or self.layout.main_scale
            if scale:
                map_item.setScale(scale)

            map_item.refresh()

    def _configure_legends(self, layout):
        for legend_spec in self.layout.legends:
            legend = layout.itemById(legend_spec.id)
            if not legend:
                messageLog(f"[LAYOUT] légende introuvable: {legend_spec.id}")
                continue

            map_item = self._get_map_item(layout, legend_spec.map)

            root = legend.model().rootGroup()
            legend.setAutoUpdateModel(False)
            root.clear()

            for key in legend_spec.layers:
                layer = self._layer(key)
                if not layer:
                    messageLog(f"[LAYOUT] couche absente de la légende '{legend_spec.id}': {key}")
                    continue
                root.addLayer(layer)

            legend.setLinkedMap(map_item)
            legend.setLegendFilterByMapEnabled(True)
            legend.refresh()

    def _add_parcels_table(self, layout):
        table_id = "table1"
        table_layer = "parca"
        field_pcl_code = seq_field("pcl_code")["name"]
        field_cor_area = seq_field("cor_area")["name"]

        table_filter = f'"{field_pcl_code}" <> \'00\''

        item = layout.itemById(table_id)
        if not item:
            return

        table = item.multiFrame() if isinstance(item, QgsLayoutFrame) else item

        layer = self._layer(table_layer)
        if not layer:
            messageLog(f"[LAYOUT] couche table absente: {table_layer}")
            return

        table.setVectorLayer(layer)
        table.setDisplayedFields([field_pcl_code, field_cor_area])
        table.setFeatureFilter(table_filter)
        table.setFilterFeatures(True)
        table.refresh()

    def _set_visibility(self):
        root = self.project.layerTreeRoot()
        root.setItemVisibilityCheckedRecursive(False)

        visible_keys = {
            key
            for map_spec in self.layout.maps
            for key in map_spec.layers
        }

        messageLog(f"Layers in layout maps: {sorted(visible_keys)}")

        for key in visible_keys:
            layer = self._layer(key)
            if not layer:
                continue

            node = root.findLayer(layer.id())
            if not node:
                continue

            node.setItemVisibilityCheckedParentRecursive(True)