from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class ProjectCanvas:
    scale: int = 1000
    zoom_on: str = ""
    readonly: list = field(default_factory=list)
    groups: list = field(default_factory=list)  # list of dicts


@dataclass
class ProjectLayout:
    theme: str = ""
    legends: list = field(default_factory=list)  # list of dicts

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


    def _flatten(self, items):
        """Flatten nested lists because [*a, *b] in yaml mean [[a], [b]]. Yaml canno't concatenate lists"""
        result = []
        for i in items:
            if isinstance(i, list):
                result.extend(self._flatten(i))
            else:
                result.append(i)
        return result

    def get_projects(self):
        data = self._load()

        return [
            (key, value.get("alias", key))
            for key, value in data.items()
        ]
    
    def get_canvas(self, key: str) -> ProjectCanvas:
        raw = self._load().get(key, {}).get("canvas", {})

        groups = []
        for g in raw.get("groups", []):
            group = dict(g)  # copy
            group["layers"] = self._flatten(g.get("layers", []))
            groups.append(group)

        return ProjectCanvas(
            scale=raw.get("scale", 1000),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            groups=groups
        )

    def get_layout(self, key: str) -> ProjectLayout:
        raw = self._load().get(key, {}).get("layout", {})

        legends = []
        for l in raw.get("legends", []):
            legend = dict(l)
            legend["layers"] = self._flatten(l.get("layers", []))
            legends.append(legend)

        return ProjectLayout(
            theme=raw.get("theme", ""),
            legends=legends
        )

