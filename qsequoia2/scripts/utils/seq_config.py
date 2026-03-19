from pathlib import Path
import urllib.request
import yaml

from .variable import get_global_variable

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

def seq_layer(key, verbose=False):
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

    if verbose:
        print(f"Resolved '{key}' → {result['full_path']}")

    return result

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

def seq_read(key, project_folder, add_to_project=False, group_name=None, style_folder=None):

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

    if layer_type == "vect":
        layer = QgsVectorLayer(str(path), layer_name, "ogr")
    elif layer_type == "rast":
        layer = QgsRasterLayer(str(path), layer_name)
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
        root = project.layerTreeRoot()

        if group_name:
            group = root.findGroup(group_name)
            if not group:
                group = root.addGroup(group_name)

            project.addMapLayer(layer, False)
            group.addLayer(layer)

        else:
            project.addMapLayer(layer)

    return layer

def find_seq_dir(root_dir):

    if not root_dir:
        return []

    root_dir = Path(root_dir)

    parca = seq_layer("parca")
    filename = parca["filename"]
    folder = parca["path"]
    
    if not folder:
        return []

    projects = {
        file.parents[1]
        for file in root_dir.rglob(f"*/{folder}/*{filename}")
    }

    return projects