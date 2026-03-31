from dataclasses import dataclass, field
from pathlib import Path
from tomlkit import key
import yaml

@dataclass
class ProjectCanvas:
    scale: int = 1000
    zoom_on: str = ""
    readonly: list = field(default_factory=list)
    layers: dict = field(default_factory=dict)  # {"seq": [...], "wmts": [...]}

@dataclass
class ProjectLayout:
    theme: str = ""
    legends: list = field(default_factory=list)

class LayoutLoader:

    def __init__(self, cfg_path: Path):
        self.cfg_path = cfg_path
        self._cache = None

    def _load(self) -> dict:
        if self._cache is None:
            if not self.cfg_path.exists():
                self._cache = {}
            else:
                with open(self.cfg_path, encoding="utf-8") as f:
                    self._cache = yaml.safe_load(f) or {}
        return self._cache

    def get_projects(self):
        data = self._load()
        return [
            (key, value.get("alias", key))
            for key, value in data.items()
        ]

    def get_canvas(self, key: str) -> ProjectCanvas:
        raw = self._load().get(key, {}).get("canvas", {})

        return ProjectCanvas(
            scale=raw.get("scale", 1000),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            layers=raw.get("layers", {})
        )

    def get_layout(self, key: str) -> ProjectLayout:
        raw = self._load().get(key, {}).get("layout", {})

        return ProjectLayout(
            theme=raw.get("theme", ""),
            legends=raw.get("legends", [])
        )
    
    def get_layers_by_type(self, key: str, layer_type: str):
        canvas = self.get_canvas(key)
        return canvas.layers.get(layer_type, [])

    def get_seq_layers(self, key: str):
        return self.get_layers_by_type(key, "seq")
    
    def get_wmts_layers(self, key: str):
        return self.get_layers_by_type(key, "wmts")