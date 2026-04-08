from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import yaml

@dataclass
class ProjectCanvas:
    key: str
    alias: str
    zoom_on: str = ""
    readonly: list[str] = field(default_factory=list)
    layers: SimpleNamespace = field(
        default_factory=lambda: SimpleNamespace(sequoia=[], tms=[],wmts=[])
    )

@dataclass
class LayoutMap:
    id: str
    layers: list[str]
    scale: int | None = None
    main_map: bool = False

@dataclass
class LegendSpec:
    id: str
    layers: list[str]
    map: str

@dataclass
class ProjectLayout:
    key: str
    main_scale: int | None = None
    maps: list[LayoutMap] = field(default_factory=list)
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
        if not value:
            return []   

        if isinstance(value, str):
            return [value]

        flat = []
        for v in value:
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
            raise TypeError(f"[CONFIG] '{key}' canvas.layers must be a dict")

        return ProjectCanvas(
            key=key,
            alias=project.get("alias", key),
            zoom_on=raw.get("zoom_on", ""),
            readonly=raw.get("readonly", []),
            layers=SimpleNamespace(
                sequoia=self._flatten(layers_raw.get("sequoia", [])),
                tms=self._flatten(layers_raw.get("tms", [])),
                wmts=self._flatten(layers_raw.get("wmts", [])),
            ),
        )

    def get_layout(self, key: str) -> ProjectLayout:
        raw = self._load().get(key, {}).get("layout", {})

        # --- maps ---
        maps_raw = raw.get("maps")
        if not isinstance(maps_raw, list) or not maps_raw:
            raise ValueError(f"[CONFIG] '{key}' layout.maps must be a non-empty list")

        maps = []
        for item in maps_raw:
            map_id = item.get("id")
            if not map_id:
                raise ValueError(f"[CONFIG] map missing 'id' in '{key}'")

            layers = self._flatten(item.get("layers", []))
            if not layers:
                raise ValueError(f"[CONFIG] map '{map_id}' has no layers")

            maps.append(
                LayoutMap(
                    id=map_id,
                    layers=layers,
                    scale=item.get("scale"),
                    main_map=item.get("main_map"),
                )
            )

        # --- duplicate ids ---
        ids = [m.id for m in maps]
        if len(ids) != len(set(ids)):
            raise ValueError(f"[CONFIG] duplicate map ids in '{key}': {ids}")

        map_ids = set(ids)

        # --- main scale ---
        main_scale = next((m.scale for m in maps if m.main_map), None)
        if main_scale is None:
            main_scale = next((m.scale for m in maps if m.scale is not None), None)

        # --- legends ---
        legends_raw = raw.get("legends", [])
        if not isinstance(legends_raw, list):
            raise TypeError(f"[CONFIG] '{key}' layout.legends must be a list")

        legends = []
        for item in legends_raw:
            legend_id = item.get("id")
            if not legend_id:
                raise ValueError(f"[CONFIG] legend missing 'id' in '{key}'")

            map_ref = item.get("map")
            if map_ref not in map_ids:
                raise ValueError(
                    f"[CONFIG] legend '{legend_id}' references unknown map '{map_ref}'"
                )

            layers = self._flatten(item.get("layers", []))
            if not layers:
                raise ValueError(f"[CONFIG] legend '{legend_id}' has no layers")

            legends.append(
                LegendSpec(
                    id=legend_id,
                    layers=layers,
                    map=map_ref,
                )
            )

        return ProjectLayout(
            key=key,
            maps=maps,
            legends=legends,
            main_scale=main_scale,
        )