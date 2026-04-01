from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import yaml

@dataclass
class LegendSpec:
    id: str
    layers: list[str] = field(default_factory=list)

@dataclass
class ProjectCanvas:
    key: str
    alias: str
    scale: int = 7500
    zoom_on: str = ""
    readonly: list[str] = field(default_factory=list)
    layers: SimpleNamespace = field(
        default_factory=lambda: SimpleNamespace(sequoia=[], wmts=[])
    )

@dataclass
class ProjectLayout:
    key: str
    scale: int = 7500
    layers: list[str] = field(default_factory=list)
    legends: list[LegendSpec] = field(default_factory=list)

class ProjectConfigLoader:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self._cache = None

    def _load(self) -> dict:
        if self._cache is None:
            with open(self.config_path, encoding="utf-8") as f:
                self._cache = yaml.safe_load(f) or {}
        return self._cache

    def _flatten(self, value) -> list:
        flat = []
        for v in value or []:
            if isinstance(v, list):
                flat.extend(self._flatten(v))
            else:
                flat.append(v)
        return flat

    def get_projects(self) -> list[tuple[str, str]]:
        data = self._load()
        return [
            (key, value.get("alias", key))
            for key, value in data.items()
        ]

    def get_canvas(self, key: str) -> ProjectCanvas:
        project = self._load().get(key, {})
        raw = project.get("canvas", {})

        layers_raw = raw.get("layers", {})
        if not isinstance(layers_raw, dict):
            layers_raw = {}

        return ProjectCanvas(
            key=key,
            alias=project.get("alias", key),
            scale=raw.get("scale", 7500),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            layers=SimpleNamespace(
                sequoia=self._flatten(layers_raw.get("sequoia", [])),
                wmts=self._flatten(layers_raw.get("wmts", [])),
            ),
        )

    def get_layout(self, key: str) -> ProjectLayout:
        raw = self._load().get(key, {}).get("layout", {})

        legends = [
            LegendSpec(
                id=item["id"],
                layers=self._flatten(item.get("layers", [])),
            )
            for item in raw.get("legends", [])
        ]

        return ProjectLayout(
            key=key,
            scale=raw.get("scale", 7500),
            layers=self._flatten(raw.get("layers", [])),
            legends=legends,
        )