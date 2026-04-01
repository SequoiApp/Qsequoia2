from pathlib import Path

from qgis.core import QgsVectorLayer, QgsRectangle, QgsWkbTypes, QgsUnitTypes, QgsPrintLayout, QgsReadWriteContext, QgsLayoutItemMap, QgsLayoutFrame, QgsLayoutItemAttributeTable
from qgis.PyQt.QtXml import QDomDocument

from qsequoia2.scripts.utils.seq_config import seq_read

# Python
from ..utils.variable import get_global_variable, get_project_variable
from ..utils.seq_config import resolve_seq_layer, seq_read
from .processing import buffer, multipart_to_singleparts
from ..utils.messageBar import messageBar, messageLog

TEMPLATE_DIR = Path(__file__).parents[2] / "data" / "templates"

class LayoutBuilder:

    FORMATS_MM = (
        ("A4", (210, 297)),
        ("A3", (297, 420)),
        ("A2", (420, 594)),
        ("A1", (594, 841)),
        ("A0", (841, 1189)),
    )

    def __init__(self, iface, project, seq_id, layout, coeff_cadre: float = 0.90):
        self.iface = iface
        self.project = project
        self.seq_id = seq_id
        self.layout = layout
        self.coeff_cadre = coeff_cadre

        self.scale = self.layout.scale
        self.layers = self.layout.layers

    def build(self):
        # compute layout info (format, orientation) from parca layer
        seq_dir = get_project_variable("QS2_seq_dir")
        if not seq_dir:
            raise RuntimeError("[Projet] Aucun projet sélectionné")

        try:
            parca = seq_read("parca", seq_dir)
        except Exception as e:
            raise RuntimeError(f"[Lecture couche 'parca'] {e}") from e

        fmt, orient = self._compute_layout_info(parca)
        
        # import layout template
        dirs = [
            Path(get_global_variable("QS2_models_directory") or ""),
            TEMPLATE_DIR,
        ]

        try:
            layout_name = self._import_layout(dirs, fmt, orient)

        except Exception as e:
            messageBar().pushCritical("Layout", str(e))
            return

        messageLog(f"Layout '{layout_name}' importé avec succès (format: {fmt}, orientation: {orient})")
        self._configure_layout(layout_name)

        return None


    def _compute_layout_info(self, parca):
        
        if not parca or not parca.isValid():
            raise ValueError("[parca] Couche invalide ou non chargée")

        if QgsWkbTypes.geometryType(parca.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise TypeError("[parca] La couche doit être polygonale")

        if parca.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
            raise TypeError("[parca] CRS non métrique → les distances peuvent être incorrectes")

        try:
            geom = self._get_main_massif(parca)
        except Exception as e:
            raise RuntimeError(f"[parca] Erreur extraction géométrie principale : {e}") from e

        if geom is None or geom.isEmpty():
            raise ValueError("[parca] Géométrie principale vide")

        bbox = geom.boundingBox()

        try:
            fmt = self._pick_format(bbox)
            orient = self._pick_orient(bbox)
        except Exception as e:
            raise RuntimeError(f"[Layout] Impossible de déterminer format/orientation : {e}") from e

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
        for name, mm in self.FORMATS_MM:
            if self._fits_bbox(mm, bbox):
                return name
        return "A0+"

    def _fits_bbox(self, mm, bbox, marge_mm=6):

        needed_w = (bbox.width() / self.scale) * 1000.0
        needed_h = (bbox.height() / self.scale) * 1000.0

        available_w = (mm[0] - 2 * marge_mm) * self.coeff_cadre
        available_h = (mm[1] - 2 * marge_mm) * self.coeff_cadre

        return needed_w <= available_w and needed_h <= available_h

    @staticmethod
    def _pick_orient(bbox):
        return "portrait" if bbox.height() >= bbox.width() else "landscape"

    def _import_layout(self, models_dirs, fmt, orient):

        try:
            qpt, orient = self._find_template(models_dirs, fmt, orient)
        except Exception as e:
            raise RuntimeError(f"[Template] {e}") from e

        layout = QgsPrintLayout(self.project)
        layout.initializeDefaults()

        doc = QDomDocument()

        try:
            with open(qpt, encoding="utf-8") as f:
                if not doc.setContent(f.read()):
                    raise ValueError("XML invalide")
        except Exception as e:
            raise RuntimeError(f"[Lecture QPT] {qpt} : {e}") from e

        try:
            layout.loadFromTemplate(doc, QgsReadWriteContext())
        except Exception as e:
            raise RuntimeError(f"[Chargement layout] {qpt} : {e}") from e

        layout_name = f"{fmt}_{orient}"

        layout.setName(layout_name)
        self.project.layoutManager().addLayout(layout)

        return layout_name

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

    def _configure_layout(self, layout_name):

        layout = self.project.layoutManager().layoutByName(layout_name)
        if not layout:
            raise RuntimeError(f"[Layout] '{layout_name}' introuvable")

        maps = [i for i in layout.items() if isinstance(i, QgsLayoutItemMap)]
        if not maps:
            raise ValueError("[Layout] Aucune carte trouvée dans le modèle")
    
        map_item = next((m for m in maps if m.id() == "map1"), maps[0])

        layout_layers = []
        for k in self.layers:
            layer = resolve_seq_layer(k, self.project, self.seq_id)
            messageLog(f"Résolution couche '{k}' → {layer.name() if layer else 'introuvable'}")
            if layer:
                layout_layers.append(layer)

        if not layout_layers:
            raise ValueError("Aucune couche valide")
        
        map_item.setFollowVisibilityPreset(False)
        map_item.setKeepLayerSet(True)
        map_item.setLayers(layout_layers)
        map_item.zoomToExtent(self.iface.mapCanvas().extent())
        map_item.setScale(self.scale)

        for legend_cfg in self.layout.legends:
            legend_id = legend_cfg.get("name")
            layer_keys = legend_cfg.get("layers", [])
            self._add_legend(layout, legend_id, layer_keys)

    def _add_legend(self, layout, legend_id, layer_keys):

        legend = layout.itemById(legend_id)
        if not legend:
            raise ValueError(f"[Legend] '{legend_id}' introuvable")

        root = legend.model().rootGroup()

        legend.setAutoUpdateModel(False)
        root.clear()

        for key in layer_keys:

            layer = resolve_seq_layer(key, self.project, self.seq_id)
            if not layer:
                continue
            root.addLayer(layer)

        legend.refresh()


#     # ====================================================
#     # AUTO TABLE CONFIG
#     # ====================================================
#     if self.project_key not in ("assemblage",):


#         path = get_path("SEQ_PF_poly", project_name= self.project_name, project_folder=self.project_folder, style_folder = self.style_folder, parent=None)

#         if path:
#             first_key = list(path.keys())[0]
#             path = path[first_key]
#             layer_name = Path(path).stem
#             layers = self.project.mapLayersByName(layer_name)

#             if layers:
#                 self.configure_attribute_table(
#                     layout=layout,
#                     table_id="table1",
#                     layer_key=layer_name,
#                     fields=["N_PARFOR", "SURF_COR"],
#                     map_id="map1",
#                     filter_expression='"N_PARFOR" <> \'00\'',)
            
#     # Import des metadata dans le layout
#     print("Metadata:", self.metadata)
#     print("Mapping config:", self.mapping_config)

#     self.apply_metadata_to_layout(layout)




# # ============================================================
# # ATTRIBUTE TABLE
# # ============================================================
# def configure_attribute_table(self,
#                               layout,
#                               table_id: str,
#                               layer_key: str,
#                               fields: list,
#                               map_id: str = None,
#                               filter_expression: str = None,):
#     """
#     Configure une table attributaire dans le layout.

#     Args:
#         layout (QgsPrintLayout): Layout contenant la table.
#         table_id (str): ID de la table.
#         layer_key (str): Clé de la couche à afficher.
#         fields (list): Liste des champs à afficher.
#         map_id (str, optional): ID de la carte pour filtrer les features visibles. Defaults to None.
#         filter_expression (str, optional): Expression de filtre QGIS. Defaults to None.

#     Raises:
#         ValueError: Si la couche ou la table est introuvable.
#     """

#     item = layout.itemById(table_id)
#     if not item:
#         pass
#     # MultiFrame support
#     if isinstance(item, QgsLayoutFrame):
#         table = item.multiFrame()
#     else:
#         table = item

#     # Résolution propre via resolve_layer
#     layer = resolve_layer(layer_key,
#                             project=self.project,
#                             project_name=self.project_name,
#                             project_folder=self.project_folder,
#                             style_folder=self.style_folder,
#                             parent=None)


#     if not layer:
#         raise ValueError(f"Couche '{layer_key}' introuvable ou non chargée")

#     # Appliquer couche + champs
#     table.setVectorLayer(layer)
#     table.setDisplayedFields(fields)

#     # Visible only
#     if map_id:
#         map_item = layout.itemById(map_id)
#         if map_item:
#             table.setMap(map_item)
#             table.setDisplayOnlyVisibleFeatures(True)

#     # Filtre
#     if filter_expression:
#         table.setFeatureFilter(filter_expression)
#         table.setFilterFeatures(True)

#     table.refresh()
    