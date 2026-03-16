
# ==========================================================================
# region import
# ==========================================================================

# python 
import os, json, yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Any


# region
# ==========================================================
# region DATA STRUCTURES
# ==========================================================

@dataclass
class ProjectCanvas:
    """
    Conteneur de données pour les paramètres de la carte d'un projet QGIS.

    Attributes:
        scale (int): Échelle du canvas (par défaut 1000).
        zoom_on (str): Clé de la couche sur laquelle zoomer.
        readonly (list): Liste des couches en lecture seule.
        groups (list): Liste des groupes de couches à créer.
        themes (list): Liste des thèmes définis dans le canvas.
    """
    scale: int = 1000
    zoom_on: str = ""
    readonly: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    themes: list = field(default_factory=list)


@dataclass
class ProjectLayout:
    """
    Conteneur de données pour les paramètres de mise en page d'un projet QGIS.

    Attributes:
        theme (str): Nom du thème par défaut pour la mise en page.
        legends (list): Liste des légendes à configurer dans le layout.
    """
    theme: str = ""
    legends: list = field(default_factory=list)

# endregion
# ==========================================================
# regionCONFIG LOADER
# ==========================================================
class ConfigLoader:
    """
    Auteur : Alexandre Le Bars, Paul Carteron, Matthieu Chevereau
    Date : 2026

    Description :
    -------------

    Fonctionnalités :
    - Chargement et mise en cache du YAML des projets.
    - Lecture des fichiers JSON de metadata, mapping et alias.
    - Accès aux informations de canvas et layout par projet.
    - Helpers pour manipuler les listes imbriquées et récupérer des valeurs par défaut.
    Charge et centralise toutes les configurations externes nécessaires au plugin QSequoia2.

    Les fichiers pris en charge :
    - YAML des projets (layoutSettings.yaml)
    - JSON de metadata du projet
    - JSON de mapping (objets layout → variables)
    - JSON d'alias de couches

    Fournit des méthodes pour :
    - Accéder aux informations de canvas et layout d’un projet.
    - Récupérer les alias et metadata.
    - Aplatir des listes imbriquées.
    - Obtenir les layers par défaut pour le thème d’un projet.

    Attributes:
        yaml_path (Path): Chemin vers le fichier layoutSettings.yaml.
        base_dir (Path): Dossier racine du plugin.
        metadata_path (Path): Chemin vers le JSON de metadata.
        mapping_path (Path): Chemin vers le JSON de mapping.
        alias_path (Path): Chemin vers le JSON des alias.
        metadata (dict): Metadata chargée depuis le JSON.
        mapping_config (dict): Mapping chargé depuis le JSON.
        layer_aliases (dict): Dictionnaire des alias de couches.

    """

    def __init__(self, yaml_path: str):
        self.yaml_path = Path(yaml_path)
        self.base_dir = self.yaml_path.parent.parent  # remonte de inst/
        self._cache_yaml = None

        # --------------------------------------------------
        # Chemins JSON et YAML
        # --------------------------------------------------
        self.metadata_path = self.base_dir / "data" / "_metadata" / "currentFolder" / "forest_metadata.json"
        self.mapping_path = self.base_dir / "inst" / "mapping.json"
        self.alias_path = self.base_dir / "inst" / "alias.json"
        self.WMTS_path = self.base_dir / "inst" / "qseq_URLS.yaml"
        

        # --------------------------------------------------
        # Charger JSON
        # --------------------------------------------------
        self.metadata = self._load_json(self.metadata_path).get("metadata", {})
        self.mapping_config = self._load_json(self.mapping_path)
        self.layer_aliases = self._load_json(self.alias_path).get("layer_aliases", {})

        # --------------------------------------------------
        # Charger YAML WMTS
        # --------------------------------------------------
        self.wmts_config = self._load_yaml(self.WMTS_path).get("wmts", {})

    # ==========================================================
    # YAML PROJECT LOADER
    # ==========================================================
    def _load_project(self) -> dict:
        """Charge et met en cache le YAML du projet. Retourne un dictionnaire vide si le fichier n'existe pas."""
        if self._cache_yaml is None:
            if not self.yaml_path.exists():
                self._cache_yaml = {}
            else:
                with open(self.yaml_path, encoding="utf-8") as f:
                    self._cache_yaml = yaml.safe_load(f) or {}
        return self._cache_yaml

    # ==========================================================
    # JSON LOADER
    # ==========================================================
    def _load_json(self, path: Path) -> dict:
        """
        Lit un fichier JSON et retourne son contenu comme dictionnaire.

        Args:
            path (Path): Chemin vers le fichier JSON.

        Returns:
            dict: Contenu du JSON ou dictionnaire vide si fichier inexistant.
        """
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content) or {}
        except json.JSONDecodeError:
            return {}

    # ==========================================================
    # YAML LOADER
    # ==========================================================
    def _load_yaml(self, path: Path) -> dict:
        """
        Charge un fichier YAML et retourne un dictionnaire.
        """
        if not path.exists():
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data or {}
        except Exception:
            return {}

    # ==========================================================
    # GETTERS YAML
    # ==========================================================

    def get_wmts_display_name(self, key: str) -> str:
        """
        Retourne le nom affiché QGIS d'un WMTS à partir de sa clé.

        Args:
            key (str): clé wmts (ex: wmts_scan25)

        Returns:
            str | None
        """
        wmts = self.wmts_config.get(key, {})
        return wmts.get("display_name")

    def get_projects(self) -> List[str]:
        """Retourne la liste des projets définis dans layoutSettings.yaml."""
        data = self._load_project()
        if not isinstance(data, dict):
            return []
        return list(data.keys())

    def get_project_canvas(self, project_key: str) -> ProjectCanvas:
        """
        Retourne un objet ProjectCanvas pour un projet donné.

        Args:
            project_key (str): Clé du projet.

        Returns:
            ProjectCanvas: Conteneur des paramètres de canvas.
        """
        raw = self._load_project().get(project_key, {}).get("canvas", {})
        return ProjectCanvas(
            scale=raw.get("scale", 1000),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            groups=raw.get("groups", []),
            themes=raw.get("themes", [])
        )

    def get_project_layout(self, project_key: str) -> ProjectLayout:
        """
        Retourne un objet ProjectLayout pour un projet donné.

        Args:
            project_key (str): Clé du projet.

        Returns:
            ProjectLayout: Conteneur des paramètres de mise en page.
        """
        raw = self._load_project().get(project_key, {}).get("layout", {})
        return ProjectLayout(
            theme=raw.get("theme", ""),
            legends=raw.get("legends", []))

    # ==========================================================
    # GETTERS JSON
    # ==========================================================
    def get_alias(self, layer_name: str) -> str:
        """
        Retourne l’alias d’une couche, ou le nom original si aucun alias défini.

        Args:
            layer_name (str): Nom de la couche.

        Returns:
            str: Alias ou nom original.
        """
        return self.layer_aliases.get(layer_name, layer_name)

    def get_metadata_key(self, key: str, default=None) -> Any:
        """
        Retourne la valeur d'une clé dans la metadata.

        Args:
            key (str): Clé recherchée.
            default (Any, optional): Valeur par défaut si la clé n'existe pas.

        Returns:
            Any: Valeur de la clé ou default.
        """
        return self.metadata.get(key, default)

    # ==========================================================
    # HELPERS
    # ==========================================================
    def flatten(self, seq: list) -> list:
        """
        Transforme une liste imbriquée en liste plate.

        Args:
            seq (list): Liste éventuellement imbriquée.

        Returns:
            list: Liste aplatie.
        """
        result = []
        for x in seq:
            if isinstance(x, list):
                result.extend(self.flatten(x))
            else:
                result.append(x)
        return result

    def get_default_layers(self, project_key: str) -> list:
        """
        Retourne les layers par défaut d’un projet selon le thème défini.

        Args:
            project_key (str): Clé du projet.

        Returns:
            list: Liste des noms de layers par défaut.
        """
        cfg = self._load_project().get(project_key, {})
        canvas = cfg.get("canvas", {})
        layout = cfg.get("layout", {})

        default_theme = layout.get("theme")
        themes = canvas.get("themes", [])

        for theme in themes:
            if theme.get("name") == default_theme:
                return self.flatten(theme.get("show", []))

        return []
    
