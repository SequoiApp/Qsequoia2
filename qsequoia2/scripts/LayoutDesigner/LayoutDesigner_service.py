
# ==========================================================================
# region import
# ==========================================================================

# python 
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Optional
import os, datetime

# QGIS
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import *
from qgis.PyQt.QtXml import QDomDocument

# Python
from ..utils.variable import get_global_variable
from ..utils.config import get_path
from .processing import buffer, multipart_to_singleparts
from ..utils.layers import resolve_layer
from .ConfigLoader import ConfigLoader
from ..utils.messageBar import messageBar

# endregion
# ============================================================
# region Data container
# ============================================================

@dataclass
class MapInfo:
    bbox: QgsRectangle
    orientation: str
    paper_format: str
    area: float


# endregion
# ==========================================================================
# region LayoutDesignerDialog
# ==========================================================================

class LayoutService:
    """
    Auteur : Alexandre Le Bars, Paul Carteron, Matthieu Chevereau
    Date : 2026

    Description :
    -------------
    Ce module fournit le service `LayoutService` pour le plugin QSequoia2 dans QGIS.
    Il centralise toutes les fonctionnalités liées à la génération et configuration
    automatique des layouts (impression/cartes) à partir des données projet.

    Fonctionnalités principales :
    - Calcul automatique du format papier optimal et de l'orientation de la carte
    selon l'emprise de la parcelle ou des couches sélectionnées.
    - Import de templates QPT et configuration du layout (carte, thème, légendes).
    - Remplissage automatique des tables attributaires dans le layout.
    - Gestion des metadata du projet et application aux éléments du layout.
    - Ajout des couches à la légende et application des alias définis.
    - Compatibilité avec les multiples projets et gestion des échelles.

    Utilitaires et dépendances :
    - `ConfigLoader` : Gestion des fichiers YAML de configuration et metadata.
    - Fonctions utilitaires : `get_global_variable`, `get_path`, `resolve_layer`, 
    `buffer`, `multipart_to_singleparts`, `messageBar`.

    Notes :
    ------
    - Destiné à être utilisé avec QGIS >= 3.40.
    - Plugin QSequoia2 pour la configuration des layouts et la
    préparation des cartes pour l'impression.
    - Toutes les variables et metadata sont persistées et réutilisées dans le layout.
    """

    FORMATS_MM: Tuple[Tuple[str, Tuple[int, int]], ...] = (
        ("A4", (210, 297)),
        ("A3", (297, 420)),
        ("A2", (420, 594)),
        ("A1", (594, 841)),
        ("A0", (841, 1189))
    )

    # ------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------

    def __init__(self, project_key: str, 
                 project, project_name, style_folder, 
                 downloads_path, project_folder, iface):
        
        self.project = project
        self.iface = iface

        # Chargement de la config

        self.script_dir = os.path.dirname(__file__)
        self.yaml_path = os.path.join(self.script_dir, "..","..","inst","layoutSettings.yaml")
        config_loader = ConfigLoader(str(self.yaml_path))
        self.config = config_loader


        # ------------------------------------------------------
        # Config centralisée
        # ------------------------------------------------------

        # Metadata, mapping, alias déjà chargés dans ConfigLoader
        self.metadata = self.config.metadata
        self.mapping_config = self.config.mapping_config
        self.layer_aliases = self.config.layer_aliases

        # Canvas / Layout YAML
        self.canvas_cfg = self.config.get_project_canvas(project_key)
        self.layout_cfg = self.config.get_project_layout(project_key)

        # ------------------------------------------------------
        # Dossiers / paths
        # ------------------------------------------------------
        self.style_folder = style_folder
        self.downloads_path = downloads_path
        self.project_folder = project_folder
        self.project_name = project_name
        self.project_key = project_key

        # Directory des modèles QPT
        self.models_dir = Path(get_global_variable("QS2_models_directory"))


    # ============================================================
    # FORMAT + ORIENTATION
    # ============================================================

    def _fits_bbox(self,mm: Tuple[int, int],
                   scale: int,
                   bbox: QgsRectangle,
                   coeff_cadre: float = 0.90,
                   marge_mm: int = 6,) -> bool:
        """
        Vérifie si une emprise (bbox) peut tenir dans un format papier donné à une échelle donnée.

        Args:
            mm (Tuple[int,int]): Dimensions du papier en mm (largeur, hauteur).
            scale (int): Échelle de la carte.
            bbox (QgsRectangle): Emprise de la zone à cartographier.
            coeff_cadre (float, optional): Coefficient de réduction de la zone utilisable. Defaults to 0.90.
            marge_mm (int, optional): Marge autour du papier en mm. Defaults to 6.

        Returns:
            bool: True si la bbox tient dans le papier, False sinon.
        """

        needed_w = (bbox.width() / scale) * 1000
        needed_h = (bbox.height() / scale) * 1000

        available_w = (mm[0] - 2 * marge_mm) * coeff_cadre
        available_h = (mm[1] - 2 * marge_mm) * coeff_cadre

        return needed_w <= available_w and needed_h <= available_h

    def _pick_format(self, scale: int, bbox: QgsRectangle, coeff=0.90) -> str:
        """
        Sélectionne le format papier minimal qui peut contenir la bbox à l'échelle donnée.

        Args:
            scale (int): Échelle de la carte.
            bbox (QgsRectangle): Emprise de la zone.
            coeff (float, optional): Coefficient de marge interne du papier. Defaults to 0.90.

        Returns:
            str: Nom du format papier choisi ("A4", "A3", … ou "A0+" si trop grand).
        """

        for name, mm in self.FORMATS_MM:
            if self._fits_bbox(mm, scale, bbox, coeff):
                return name

        return "A0+"

    def _pick_orientation(self, bbox: QgsRectangle) -> str:
        """
        Détermine l’orientation (portrait ou paysage) pour une bbox.

        Args:
            bbox (QgsRectangle): Emprise de la zone.

        Returns:
            str: "portrait" ou "landscape".
        """
        return "portrait" if bbox.height() >= bbox.width() else "landscape"

    # ============================================================
    # COMPUTE MAP INFO
    # ============================================================

    def compute_layout_info(self,uri: Optional[str] = None,
                            scale: int = 15000,
                            snap_distance: int = 200,
                            coeff_cadre: float = 0.90,
                            provider: str = "ogr",) -> MapInfo:
        """
        Calcule les informations de mise en page à partir d'une couche vectorielle.

        Effectue le buffer/dissolve, sélectionne le plus grand polygone, et calcule
        le format et l’orientation du layout.

        Args:
            uri (Optional[str], optional): URI de la couche à utiliser. Defaults to None.
            scale (int, optional): Échelle de la carte. Defaults to 15000.
            snap_distance (int, optional): Distance de buffer en mètres. Defaults to 200.
            coeff_cadre (float, optional): Coefficient de réduction pour le cadre. Defaults to 0.90.
            provider (str, optional): Fournisseur de données (ogr, etc.). Defaults to "ogr".

        Raises:
            ValueError: Si la couche est invalide ou aucune géométrie trouvée.
            TypeError: Si la couche n’est pas polygonale.

        Returns:
            MapInfo: Contient bbox, orientation, format papier et surface.
        """

        if uri is None:
            layer_dict = get_path("SEQ_PARCA_poly", project_name=self.project_name, project_folder=self.project_folder, style_folder=self.style_folder, parent=None)
        
        if not layer_dict:
            raise ValueError(f"URI invalide : {uri}")
        uri = list(layer_dict.values())[0]

        layer = QgsVectorLayer(uri, "tmp", provider)

        if not layer.isValid():
            raise ValueError(f"Layer invalide : {uri}")

        if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            raise TypeError("Layer doit être polygonal")

        if layer.crs().mapUnits() != QgsUnitTypes.DistanceMeters:
            messageBar(self.iface, "buffer interprété en unités CRS (pas mètres)", "w",10)

        # --- PROCESS ---
        buffered = buffer(layer, distance=snap_distance / 2, dissolve=True)

        dissolved = buffer(buffered, distance=-snap_distance / 2)

        single_parts = multipart_to_singleparts(dissolved)


        feat = max(single_parts.getFeatures(),
                   key=lambda f: f.geometry().area(),
                   default=None,)

        if feat is None or feat.geometry().isEmpty():
            raise ValueError("Aucune géométrie valide trouvée")

        geom = feat.geometry()
        bbox = geom.boundingBox()


        fmt = self._pick_format(scale, bbox, coeff_cadre)
        orient = self._pick_orientation(bbox)



        return MapInfo(bbox=bbox,orientation=orient,paper_format=fmt,area=geom.area())


    # ============================================================
    # TEMPLATE IMPORT
    # ============================================================

    def _find_template(self, fmt: str, orient: str):
        """
        Cherche le template QPT correspondant au format et à l’orientation.

        Args:
            fmt (str): Format papier (A4, A3, …).
            orient (str): Orientation ("portrait" ou "landscape").

        Returns:
            Tuple[Path, str]: Chemin du template et orientation utilisée.

        Raises:
            FileNotFoundError: Si aucun template n’est trouvé.
        """

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
        """
        Importe un layout depuis un fichier template QPT.

        Args:
            project_key (str): Clé du projet utilisé pour le nommage.
            fmt (str): Format papier choisi.
            orient (str): Orientation choisie.

        Returns:
            QgsPrintLayout: Layout initialisé et prêt à être configuré.
        """

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
            # lecture des metadata pour trouver les départements
            deps = self.metadata["departement_str"]
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

    def configure_layout(self,
                         layout: QgsPrintLayout,
                         theme: str = None,
                         scale: int = None,
                         legends: list = None,
                         hide_legend_names: bool = False,):
        """
        Configure le layout : carte, échelle, thème, légendes, et table attributaire.

        Args:
            layout (QgsPrintLayout): Layout à configurer.
            theme (str, optional): Thème à appliquer aux couches. Defaults to None.
            scale (int, optional): Échelle de la carte. Defaults to None.
            legends (list, optional): Liste de légendes à configurer. Defaults to None.
            hide_legend_names (bool, optional): Masque les noms des couches. Defaults to False.
        """
        print("configure_layout START", self.project_key)
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
                self.add_layer_to_legend(layout=layout,
                                         legend_id=l["name"],
                                         layer_keys=l["layers"],
                                         map_id="map1",
                                         )

        # ====================================================
        # AUTO TABLE CONFIG
        # ====================================================
        if self.project_key not in ("assemblage",):


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
        print("Metadata:", self.metadata)
        print("Mapping config:", self.mapping_config)

        self.apply_metadata_to_layout(layout)

    # ============================================================
    # LEGEND
    # ============================================================
    def add_layer_to_legend(self,layout,
                            legend_id: str,
                            layer_keys: list,
                            map_id: str = None,):
        """
        Ajoute des couches à une légende dans le layout et applique les alias.

        Args:
            layout (QgsPrintLayout): Layout contenant la légende.
            legend_id (str): ID de la légende.
            layer_keys (list): Clés des couches à ajouter.
            map_id (str, optional): ID de la carte liée. Defaults to None.

        Raises:
            ValueError: Si la légende n’est pas trouvée.
        """

        legend = layout.itemById(legend_id)
        if not legend:
            raise ValueError(f"Légende '{legend_id}' introuvable")

        root = legend.model().rootGroup()

        # ---------------------------
        # Aplatir layer_keys
        # ---------------------------
        if hasattr(self.config, "flatten"):
            flat_keys = self.config.flatten(layer_keys)
        else:
            # fallback simple
            flat_keys = []
            for k in layer_keys:
                if isinstance(k, list):
                    flat_keys.extend(k)
                else:
                    flat_keys.append(k)

        # ---------------------------
        # Boucle sur chaque clé
        # ---------------------------
        for key in flat_keys:

            # Résolution du layer
            layer = resolve_layer(
                key,
                self.project,
                project_name=self.project_name,
                project_folder=self.project_folder,
                style_folder=self.style_folder,
                parent=None,
            )

            if not layer:
                continue  # Skip if not found

            # Eviter doublon
            if layer.id() in [n.layerId() for n in root.findLayers()]:
                continue

            # Ajouter layer dans la légende
            node = root.addLayer(layer)

            # Appliquer alias si existant
            alias = None
            if isinstance(key, str):
                alias = self.layer_aliases.get(key)

            if alias:
                node.setName(alias)
            else:
                node.setName(layer.name())  # fallback si pas d'alias

        # ---------------------------
        # Filtrage sur une map spécifique
        # ---------------------------
        if map_id:
            map_item = layout.itemById(map_id)
            legend.setLinkedMap(map_item)
            legend.setLegendFilterByMapEnabled(True)

        legend.refresh()

    # ============================================================
    # ATTRIBUTE TABLE
    # ============================================================
    def configure_attribute_table(self,
                                  layout,
                                  table_id: str,
                                  layer_key: str,
                                  fields: list,
                                  map_id: str = None,
                                  filter_expression: str = None,):
        """
        Configure une table attributaire dans le layout.

        Args:
            layout (QgsPrintLayout): Layout contenant la table.
            table_id (str): ID de la table.
            layer_key (str): Clé de la couche à afficher.
            fields (list): Liste des champs à afficher.
            map_id (str, optional): ID de la carte pour filtrer les features visibles. Defaults to None.
            filter_expression (str, optional): Expression de filtre QGIS. Defaults to None.

        Raises:
            ValueError: Si la couche ou la table est introuvable.
        """

        item = layout.itemById(table_id)
        if not item:
            pass
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
        vars_dict["username"] = get_global_variable("QS2_user_full_name")
        vars_dict["adresse"] = get_global_variable("QS2_adress_organisation")
        vars_dict["project_alias"] = self.get_project_alias(self.project_key)

        return vars_dict


    def apply_metadata_to_layout(self, layout):
        """
        Remplit les éléments du layout avec les variables et metadata du projet.

        Args:
            layout (QgsPrintLayout): Layout à remplir.
        """

        all_vars = self.build_available_variables()

        combined_mapping = {}
        combined_mapping.update(self.mapping_config.get("metadata", {}))
        combined_mapping.update(self.mapping_config.get("var", {}))
        print("combined_mapping ", combined_mapping)

        for obj_name, config in combined_mapping.items():

            item = layout.itemById(obj_name)
            if not item:
                print("manquant : ", obj_name)
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

    ### Récupération des alias

    def get_project_alias(self, project_key: str) -> str:
        """
        Retourne l'alias du projet tel que défini dans le YAML.

        Args:
            project_key (str): Clé du projet.

        Returns:
            str: Alias du projet ou la clé si aucun alias n’existe.
        """
        project_config = self.config._load_project().get(project_key, {})
        # Vérifie si 'un projet' existe et contient 'alias'
        alias = project_config.get("alias",self.project_key)
        if alias:
            return alias
        return project_key
