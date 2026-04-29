from pathlib import Path

from qgis.PyQt.QtXml import QDomDocument
from qgis.core import (
    QgsLayoutFrame,
    QgsLayoutItem,
    QgsLayoutItemMap,
    QgsLayoutItemLegend,
    QgsPrintLayout,
    QgsReadWriteContext,
    QgsRectangle,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsLayoutTableColumn
)

from qgis.PyQt.QtWidgets import QMessageBox

from ..utils.Qmessage import messageBar, messageLog
from ..utils.variable import get_global_variable, get_project_variable, set_project_variable
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
        seq_dir = get_project_variable("QS2_seq_dir") or None
        parca = seq_read("parca", seq_dir=seq_dir, add_to_project=False)
        if not parca:
            raise RuntimeError("[LAYOUT] Couche 'parca' absente du contexte")


        fmt, orient, bbox = self._compute_layout_info(parca)
        set_project_variable("QS2_layout_format", fmt)
        set_project_variable("QS2_layout_orient", orient)
        
        layout_name, qpt = self._create_layout_name(fmt, orient)

        layout = self._resolve_layout(layout_name)
        if layout:
            return layout

        layout = self._create_layout(layout_name, qpt)

        self._configure_maps(layout, bbox)
        self._configure_legends(layout)
        self._add_parcels_table(layout)
        self._hide_unused_template_items(layout)
        self._set_visibility()

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

        return fmt, orient, bbox

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

    def _resolve_layout(self, layout_name):
        lm = self.project.layoutManager()
        existing = lm.layoutByName(layout_name)

        if not existing:
            return None

        overwrite = QMessageBox.question(
            self.iface.mainWindow(),
            "Layout existant",
            f"Le layout '{layout_name}' existe déjà.\nVoulez-vous l'écraser ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if overwrite == QMessageBox.No:
            return existing

        try:
            self.iface.closeLayoutDesigner(existing)
        except Exception:
            pass

        lm.removeLayout(existing)
        return None

    def _create_layout_name(self, fmt: str, orient: str):
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
        return layout_name, qpt

    def _create_layout(self, layout_name, qpt) -> QgsPrintLayout:
        lm = self.project.layoutManager()

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
            messageLog(f"[Layout] Carte '{map_id}' introuvable")
            raise RuntimeError(f"Carte '{map_id}' introuvable")

        if not isinstance(item, QgsLayoutItemMap):
            messageLog(f"Carte '{map_id}' introuvable")
            raise RuntimeError(f"Carte '{map_id}' introuvable")

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

    def _configure_maps(self, layout, bbox):

        for map_spec in self.layout.maps:
            map_item = self._get_map_item(layout, map_spec.id)
            messageLog(f"[LAYOUT] configuring: {map_spec.id} with layers: {map_spec.layers} (main_map={map_spec.main_map})")

            map_item.setFollowVisibilityPreset(False)
            map_item.zoomToExtent(bbox)    

            if map_spec.main_map:
                map_item.setKeepLayerSet(False)
            else:
                map_item.setKeepLayerSet(True)
                map_layers = self._resolve_map_layers(map_spec)
                map_item.setLayers(map_layers)

            # scale (common logic)
            scale = map_spec.scale
            messageLog(f"[SCALE] scale:{scale} - map_item:{map_item}")
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
        table_layer_key = "v.seq.pf.poly"

        field_pcl_code = seq_field("pcl_code")["name"]
        field_cor_area = seq_field("cor_area")["name"]

        table_filter = f'"{field_pcl_code}" <> \'00\''

        item = layout.itemById(table_id)
        if not item:
            return

        table = item.multiFrame() if isinstance(item, QgsLayoutFrame) else item

        layer = self._layer(table_layer_key)
        if not layer:
            messageLog(f"[LAYOUT] couche table absente: {table_layer_key}")
            return

        columns = []

        col = QgsLayoutTableColumn()
        col.setAttribute(field_pcl_code)
        col.setHeading("Parcelle")
        columns.append(col)

        col = QgsLayoutTableColumn()
        col.setAttribute(field_cor_area)
        col.setHeading("Surface (ha)")
        columns.append(col)

        table.setVectorLayer(layer)
        table.setColumns(columns)
        table.setFeatureFilter(table_filter)
        table.setFilterFeatures(True)
        table.refresh()

    def _set_visibility(self):
        root = self.project.layerTreeRoot()
        root.setItemVisibilityCheckedRecursive(False)

        main_maps = [m for m in self.layout.maps if m.main_map]

        if len(main_maps) != 1:
            raise ValueError(f"Expected exactly one main map, found {len(main_maps)}.")

        for key in main_maps[0].layers:
            layer = self._layer(key)
            if not layer:
                continue

            node = root.findLayer(layer.id())
            if node:
                node.setItemVisibilityCheckedParentRecursive(True)

    def _hide_unused_template_items(self, layout):
        """Hide template maps and legends not declared in layout config."""

        configured_map_ids = {m.id for m in self.layout.maps}
        configured_legend_ids = {l.id for l in self.layout.legends}

        for item in list(layout.items()):
            if not isinstance(item, QgsLayoutItem):
                continue

            item_id = item.id()

            if not item_id:
                continue

            if isinstance(item, QgsLayoutItemMap) and item_id not in configured_map_ids:
                item.setVisibility(False)
                messageLog(f"[LAYOUT] Hidden unused map item: {item_id}")

            elif isinstance(item, QgsLayoutItemLegend) and item_id not in configured_legend_ids:
                item.setVisibility(False)
                messageLog(f"[LAYOUT] Hidden unused legend item: {item_id}")