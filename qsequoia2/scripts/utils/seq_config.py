from pathlib import Path
import urllib.request
import yaml
import os
from .messageBar import messageBar, messageLog

from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProject
)


_BASE_URL = "https://raw.githubusercontent.com/SequoiApp/Rsequoia2/main/inst/config"

_SEQ_CONFIG_URLS = {
    key: f"{_BASE_URL}/{key}.yaml"
    for key in ["seq_fields", "seq_layers", "seq_path", "seq_tables"]
}

_CACHE_DIR = Path(QgsApplication.qgisSettingsDirPath()) / "qsequoia2"

_CONFIG_CACHE = {}

# TODO plus propre dans une class

def sync_seq_configs(timeout: int = 3) -> None:
    """
    Download latest configs to cache.

    - Silent if offline
    - Safe to call at plugin startup
    """

    _CACHE_DIR.mkdir(exist_ok=True)

    for key, url in _SEQ_CONFIG_URLS.items():
        path = _CACHE_DIR / f"{key}.yaml"

        try:
            response = urllib.request.urlopen(url, timeout=timeout)
            content = response.read().decode("utf-8")
            path.write_text(content, encoding="utf-8")

        except Exception:
            # Silent fallback
            pass
    
    return None

def get_seq_config_path(name: str) -> Path:
    """
    Return cached config path.

    Raises:
        RuntimeError if config is missing (first run offline)
    """

    path = _CACHE_DIR / f"{name}.yaml"

    if path.exists():
        return path

    raise RuntimeError(
        f"Config '{name}' not found.\n"
        "You need an internet connection for the first plugin use."
    )

def get_seq_config(name: str) -> dict:
    if name in _CONFIG_CACHE:
        return _CONFIG_CACHE[name]

    path = get_seq_config_path(name)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        raise ValueError(f"Empty config: {name}")

    _CONFIG_CACHE[name] = data
    return data

def seq_key(key):
    """Return exactly one matching key from config."""

    cfg_layer = get_seq_config("seq_layers")
    all_keys = list(cfg_layer.keys())

    matches = [k for k in all_keys if key in k]

    if not matches:
        raise ValueError(f"Key '{key}' not found.")

    if len(matches) > 1:
        raise ValueError(f"Multiple matches for '{key}': {matches}")

    return matches[0]

def seq_layer(key):
    """Resolve a Sequoia layer key to metadata."""

    cfg_layer = get_seq_config("seq_layers")
    cfg_path = get_seq_config("seq_path")

    match_key = seq_key(key) 

    layer = cfg_layer[match_key]

    filename = f"{layer['name']}.{layer['ext']}"

    # resolve family
    family = None
    for ns, fam in cfg_path["namespace"].items():
        if match_key.startswith(ns):
            family = fam
            break

    path = cfg_path["path"].get(family) if family else None
    full_path = Path(path) / filename if path else None

    # detect type
    prefix = match_key.split(".")[0]

    type_map = {
        "v": "vect",
        "r": "rast",
        "x": "xlsx"
    }

    layer_type = type_map.get(prefix)

    result = {
        "key": match_key,
        "name": layer["name"],
        "ext": layer["ext"],
        "filename": filename,
        "family": family,
        "path": path,
        "full_path": str(full_path) if full_path else None,
        "type": layer_type
    }

    return result

def resolve_seq_layer(key, project, seq_id=None):
    meta = seq_layer(key)

    filename = meta["filename"]
    if seq_id:
        filename = f"{seq_id}_{filename}"

    expected_dir = meta["path"]

    for layer in project.mapLayers().values():
        messageLog(f"Checking layer '{layer.name()}' with source '{layer.source()}'...")
        source = layer.source().split("|")[0]  # remove provider suffix : path|layername=...
        path = Path(source)

        if path.name == filename and expected_dir in path.parts:
            return layer

    return None

def seq_field(field: str) -> dict:

    cfg = get_seq_config("seq_fields")

    # Return full config
    if field is None:
        return cfg

    # Validate key
    if field not in cfg:
        raise ValueError(
            f"Field '{field}' does not exist.\n"
            "Valid keys are defined in seq_fields.yaml.\n"
            "This file is managed by Rsequoia2 and must not be modified."
        )

    return cfg[field]

def get_style(layer_key, style_folder):

    if not style_folder:
        raise ValueError("'styles_directory' is not set")

    style_dir = Path(style_folder)
    if not style_dir.is_dir():
        return None

    layer = seq_layer(layer_key)
    layer_name = layer["name"]

    # Expected style filename
    target = f"{layer_name}.qml"

    # Recursive search
    for path in style_dir.rglob(target):
        return str(path)

    return None


def seq_read(key, project_folder, add_to_project=False, group=None, style_folder=None):

    meta = seq_layer(key)
    layer_type = meta["type"]
    layer_name = meta["name"]
    filename = meta["filename"]

    project_folder = Path(project_folder)

    matches = list(project_folder.rglob(f"*{filename}"))
    if not matches:
        raise FileNotFoundError(f"Layer '{filename}' not found in '{project_folder}'")

    if len(matches) > 1:
        paths_str = "\n".join(str(p) for p in matches)
        raise RuntimeError(
            f"Multiple layers found for '{filename}':\n{paths_str}"
        )

    path = matches[0]
    path_str = str(path)

    # Check if layer already exists in the group
    if group:
        for node in group.findLayers():
            existing_layer = node.layer()
            if existing_layer and existing_layer.source().startswith(path_str):
                messageLog(f"Layer already in group: '{existing_layer.name()}' ({existing_layer.source()})")
                messageBar(f"Layer {existing_layer.name()} already in group: '{group.name()}'")
                return existing_layer

    if layer_type == "vect":
        layer = QgsVectorLayer(path_str, layer_name, "ogr")
    elif layer_type == "rast":
        layer = QgsRasterLayer(path_str, layer_name)
    else:
        raise ValueError(f"Unsupported layer type: {layer_type}")

    if not layer.isValid():
        raise RuntimeError(f"Invalid layer: {path}")


    if style_folder:
        style_path = get_style(key, style_folder)
        if style_path:
            layer.loadNamedStyle(style_path)
            layer.triggerRepaint()

    if add_to_project:
        project = QgsProject.instance()
        project.addMapLayer(layer, not bool(group))

        if group:
            group.addLayer(layer)

    return layer

def find_all_seq_dir(root_dir, max_dirs=5000):
    """
    Efficiently find Sequoia project directories.

    - Limits traversal to `max_dirs` to avoid scanning huge trees
    - Detects Sequoia folders early (no need to descend into them)
    - Assumes no Sequoia folder is nested inside another

    """

    if not root_dir:
        return []

    root_dir = Path(root_dir)

    parca = seq_layer("parca")
    filename = parca["filename"]
    folder = parca["path"]
    folder_name = Path(folder).name

    projects = set()
    visited = 0

    for root, dirs, _ in os.walk(root_dir):

        visited += 1
        if visited >= max_dirs:
            raise RuntimeError(
                f"Search aborted: more than {max_dirs} directories visited. "
                "Please narrow the search root."
            )

        root_path = Path(root)

        #  detect Sequoia folder early
        if folder_name in dirs:
            seq_path = root_path / folder_name

            # prevent descending into Sequoia folder
            dirs.remove(folder_name)

            for f in seq_path.iterdir():
                if f.is_file() and f.name.endswith(filename):
                    try:
                        projects.add(root_path)
                    except IndexError:
                        pass

    return projects

def find_seq_id(seq_dir):
    layer = seq_read("parca", seq_dir)
    field_name = seq_field("identifier")["name"]

    # set() ensure uniqueness
    identifiers = set()
    for feat in layer.getFeatures():
        value = feat[field_name]
        if value:
            identifiers.add(value)

    if not identifiers:
        raise RuntimeError(
            f"Aucun identifiant trouvé dans le champ '{field_name}'."
        )

    if len(identifiers) > 1:
        raise RuntimeError(
            f"Plusieurs identifiants trouvés dans le champ '{field_name}' : {identifiers}"
    )

    return identifiers.pop()
