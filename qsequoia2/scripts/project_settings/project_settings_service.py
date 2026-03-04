from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Optional, List

import os, datetime,json
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

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
        self.project_key = project_key



        self.models_dir = Path(get_global_variable("models_directory"))

        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        # Metadata

        metadata_path = os.path.join(self.script_dir, "..","..","data","_metadata","currentFolder","forest_metadata.json")

        with open(metadata_path, 'r', encoding='utf-8') as f:
            data_json = json.load(f)

        # Extraire proprement la clé "metadata"
        self.metadata = data_json.get("metadata", {})

        # Mapping config

        mapping_json = os.path.join(self.script_dir,"mapping.json")

        # Charger la config
        with open(mapping_json, 'r', encoding='utf-8') as f:
            mapping_config = json.load(f)

        self.mapping_config = mapping_config


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

        # Nom de la carte courante 

        # Année courante
        years = datetime.datetime.now().year

        # build des noms
        try :
            # import de forest_stat pour les département
            forest_stats = ForestStat(project=QgsProject.instance(),project_name=self.project_name,project_folder=self.project_folder,style_folder=self.style_folder,iface=self.iface)
            departements = forest_stats.forest_departements(layers = 'SEQ_PARCA_poly',project_name=self.project_name,project_folder=self.project_folder,style_folder=self.style_folder)

            deps = str(departements.replace(" ","").replace("&","-").replace(",","-"))
            layout.setName(f"{deps}-{self.project_name.upper()}-{project_key}-{years}_{fmt}_{orient_used}")
        except:
            layout.setName(f"{self.project_name.upper()}-{project_key}-{years}_{fmt}_{orient_used}")
        
        # Test si un projet du même nom existe deja
        manager = QgsProject.instance().layoutManager()

        if manager.layoutByName(layout.name()):

            QMessageBox.critical(
                self.iface.mainWindow(),
                "Mise en page déjà existante",
                f"Une mise en page nommée :\n\n"
                f"{layout.name()}\n\n"
                "existe déjà dans ce projet.\n\n"
                "Veuillez supprimer ou renommer l'existante avant de continuer."
            )

            return


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
                    filter_expression='"N_PARFOR" <> \'00\'',)
                
        # Import des metadata dans le layout
        self.apply_metadata_to_layout(layout)

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
        
    # ============================================================
    # Ajout des metadata dans la layout et des variables
    # ============================================================

    def build_available_variables(self):

        vars_dict = {}

        # JSON racine
        #vars_dict.update(self.root_data)

        # metadata
        vars_dict.update(self.metadata)

        # variables internes Python
        vars_dict["project_key"] = self.project_key
        vars_dict["current_date"] = datetime.datetime.now().strftime("%m/%Y")
        vars_dict["username"] = get_global_variable("user_full_name")
        vars_dict["adress"] = get_global_variable("adress_organisation")  # si défini ailleurs

        return vars_dict


    def apply_metadata_to_layout(self, layout):
        """
        Assigne les valeurs du JSON data_json aux éléments de layout selon mapping_json
        layout : QgsLayout
        data_json : dictionnaire avec tes données (le JSON du projet)
        mapping_json : dictionnaire {objectName_layout: variable_data_json}
        """

        all_vars = self.build_available_variables()

        combined_mapping = {}
        combined_mapping.update(self.mapping_config.get("metadata", {}))
        combined_mapping.update(self.mapping_config.get("var", {}))

        for obj_name, config in combined_mapping.items():

            item = layout.itemById(obj_name)
            if not item:
                continue

            # Si mapping simple
            if isinstance(config, str):
                value = all_vars.get(config, "")

            # Si mapping avancé (avec prefix)
            elif isinstance(config, dict):
                var_name = config.get("var")
                value = all_vars.get(var_name, "")

                prefix = config.get("prefix", "")
                suffix = config.get("suffix", "")

                value = f"{prefix}{value}{suffix}"

            else:
                value = ""

            if isinstance(value, float):
                value = f"{value:.4f}"

            item.setText(str(value))
            