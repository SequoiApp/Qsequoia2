from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Optional, Union

import tomllib

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
    scale: Optional[int] = None
    main_map: bool = False

@dataclass
class LegendSpec:
    id: str
    layers: list[str]
    map: str

@dataclass
class ProjectLayout:
    key: str
    main_scale: Optional[int] = None
    maps: list[LayoutMap] = field(default_factory=list)
    legends: list[LegendSpec] = field(default_factory=list)

class ProjectConfigLoader:
    """Read one project per TOML file, using its filename field as the project key."""

    def __init__(self, config_dir: Union[str, Path]):
        self.config_dir = Path(config_dir).expanduser()
        self._cache = None

    def _load(self) -> dict:
        if self._cache is None:
            if not self.config_dir.is_dir():
                raise ValueError(f"[CONFIG] Dossier introuvable : {self.config_dir}")

            projects = {}
            project_files = {}
            for config_file in sorted(self.config_dir.glob("*.toml")):
                try:
                    with config_file.open("rb") as f:
                        config = tomllib.load(f)
                except (OSError, tomllib.TOMLDecodeError) as err:
                    raise ValueError(f"[CONFIG] {config_file}: {err}") from err

                key = config.get("filename", "")
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(f"[CONFIG] {config_file.name} : filename doit être un texte non vide")
                key = key.strip()
                if key in projects:
                    raise ValueError(
                        f"[CONFIG] filename '{key}' déjà utilisé dans deux fichiers :\n"
                        f"- {project_files[key]}\n"
                        f"- {config_file.resolve()}"
                    )
                projects[key] = config
                project_files[key] = config_file.resolve()

            if not projects:
                raise ValueError(f"[CONFIG] Aucun fichier .toml dans : {self.config_dir}")

            self._cache = projects
        return self._cache

    def get_projects(self) -> list[tuple[str, str]]:
        projects = []
        for key, config in self._load().items():
            alias = config.get("alias", key)
            if not isinstance(alias, str):
                raise ValueError(f"[CONFIG] Projet '{key}' : alias doit être un texte")
            projects.append((key, alias))
        return projects

    def get_canvas(self, key: str) -> ProjectCanvas:
        project = self._load()[key]
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
                sequoia=layers_raw.get("sequoia", []),
                tms=layers_raw.get("tms", []),
                wmts=layers_raw.get("wmts", []),
            ),
        )

    def get_layout(self, key: str) -> ProjectLayout:
        raw = self._load()[key].get("layout", {})

        # --- maps ---
        maps_raw = raw.get("maps")
        if not isinstance(maps_raw, list) or not maps_raw:
            raise ValueError(f"[CONFIG] '{key}' layout.maps must be a non-empty list")

        maps = []
        for item in maps_raw:
            map_id = item.get("id")
            if not map_id:
                raise ValueError(f"[CONFIG] map missing 'id' in '{key}'")

            layers = item.get("layers", [])
            if not isinstance(layers, list) or not layers:
                raise ValueError(f"[CONFIG] map '{map_id}' has no layers")

            maps.append(
                LayoutMap(
                    id=map_id,
                    layers=layers,
                    scale=item.get("scale"),
                    main_map=item.get("main_map", False),
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

            layers = item.get("layers", [])
            if not isinstance(layers, list) or not layers:
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
