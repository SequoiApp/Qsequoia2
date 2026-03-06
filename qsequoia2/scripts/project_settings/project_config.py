import yaml
from dataclasses import dataclass, field


# ==========================================================
# DATA STRUCTURES
# ==========================================================

@dataclass
class ProjectCanvas:
    scale: int = 1000
    zoom_on: str = ""
    readonly: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    themes: list = field(default_factory=list)


@dataclass
class ProjectLayout:
    theme: str = ""
    legends: list = field(default_factory=list)


# ==========================================================
# CONFIG LOADER
# ==========================================================

class ProjectConfig:

    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self._cache = None

    # ==========================================================
    # YAML PROJECT CONFIG
    # ==========================================================

    def _load_project(self):
        """Charge project.yaml une seule fois"""
        if self._cache is None:
            with open(self.yaml_path, encoding="utf-8") as f:
                self._cache = yaml.safe_load(f) or {}
        return self._cache

    # ==========================================================
    # GETTERS
    # ==========================================================

    def get_project_canvas(self, name: str) -> ProjectCanvas:

        raw = self._load_project().get(name, {}).get("canvas", {})

        return ProjectCanvas(
            scale=raw.get("scale", 1000),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            groups=raw.get("groups", []),
            themes=raw.get("themes", []),
        )

    def get_project_layout(self, name: str) -> ProjectLayout:

        raw = self._load_project().get(name, {}).get("layout", {})

        return ProjectLayout(
            theme=raw.get("theme", ""),
            legends=raw.get("legends", []),
        )

    # ==========================================================
    # HELPERS
    # ==========================================================

    def flatten(self, seq):
        """Transforme une liste imbriquée en liste simple"""
        result = []
        for x in seq:
            if isinstance(x, list):
                result.extend(self.flatten(x))
            else:
                result.append(x)
        return result

    def get_default_layers(self, project_name: str):

        cfg = self._load_project().get(project_name, {})

        canvas = cfg.get("canvas", {})
        layout = cfg.get("layout", {})

        default_theme = layout.get("theme")
        themes = canvas.get("themes", [])

        for theme in themes:
            if theme["name"] == default_theme:
                return self.flatten(theme.get("show", []))

        return []
