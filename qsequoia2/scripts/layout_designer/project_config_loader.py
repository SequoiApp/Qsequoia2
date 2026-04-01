from dataclasses import dataclass, field
from types import SimpleNamespace
from pathlib import Path
import yaml

@dataclass
class ProjectCanvas:
    key: str = ""
    alias: str = ""
    zoom_on: str = ""
    readonly: list = field(default_factory=list)
    layers: SimpleNamespace = field(default_factory=SimpleNamespace)

@dataclass
class ProjectLayout:
    scale: int = 7500
    layers: list = field(default_factory=list)
    legends: list = field(default_factory=list)

class ProjectConfigLoader:

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

    def _flatten(self, value):
        if not isinstance(value, list):
            return []

        flat = []
        for v in value:
            if isinstance(v, list):
                flat.extend(v)
            else:
                flat.append(v)
        return flat

    def get_projects(self):
        data = self._load()
        return [
            (key, value.get("alias", key))
            for key, value in data.items()
        ]
    
    def get_canvas(self, key: str) -> ProjectCanvas:
        data = self._load()
        project = data.get(key, {})

        raw = project.get("canvas", {})

        layers_raw = raw.get("layers", {})
        if not isinstance(layers_raw, dict):
            layers_raw = {}

        return ProjectCanvas(
            key=key,
            alias=project.get("alias", key),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            layers=SimpleNamespace(**layers_raw)
        )

    def get_layout(self, key: str) -> ProjectLayout:
        raw = self._load().get(key, {}).get("layout", {})

        layers = self._flatten(raw.get("layers", []))

        legends = raw.get("legends", [])
        if isinstance(legends, list):
            for l in legends:
                if isinstance(l, dict):
                    l["layers"] = self._flatten(l.get("layers", []))

        return ProjectLayout(
            scale=raw.get("scale", 7500),
            layers=layers,
            legends=legends
        )
        