from pathlib import Path
from urllib.parse import urlparse
import urllib.request
import yaml
import os

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsProviderRegistry

from .layer_tree import get_group
from .plugin_vars import CONFIG_CACHE
from .Qmessage import messageLog, messageBar
from .alias import get_alias

_BASE_URL = "https://raw.githubusercontent.com/SequoiApp/Rsequoia2/main/inst/config"

_SEQ_CONFIG_URLS = {
    key: f"{_BASE_URL}/{key}.yaml"
    for key in ["seq_fields", "seq_layers", "seq_path", "seq_tables"]
}

_CACHE_DIR = Path(QgsApplication.qgisSettingsDirPath()) / "qsequoia2"


def _safe_urlopen(url, timeout=10):
    parsed = urlparse(url)

    if parsed.scheme not in ["http", "https"]:
        raise ValueError(f"Blocked unsafe URL scheme: {parsed.scheme}")

    return urllib.request.urlopen(url, timeout=timeout)


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
            response = _safe_urlopen(url, timeout=timeout)
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
    if name in CONFIG_CACHE:
        return CONFIG_CACHE[name]

    path = get_seq_config_path(name)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        raise ValueError(f"Empty config: {name}")

    CONFIG_CACHE[name] = data
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
        "alias": get_alias(match_key) or layer["name"],
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

def _norm_project_path(raw_path, project=None):
    project = project or QgsProject.instance()
    if not raw_path:
        return None

    raw_path = project.readPath(str(raw_path))
    return os.path.normcase(os.path.normpath(str(Path(raw_path).resolve())))

def _vector_file_path(layer, project=None):
    project = project or QgsProject.instance()
    parts = QgsProviderRegistry.instance().decodeUri(
        layer.providerType(),
        layer.source(),
    )
    return _norm_project_path(parts.get("path"), project)

def _raster_file_path(layer, project=None):
    project = project or QgsProject.instance()
    raw = layer.dataProvider().dataSourceUri() or layer.source()
    return _norm_project_path(raw, project)

def _find_existing_seq_layer(path, layer_type, group=None):
    project = QgsProject.instance()
    target = _norm_project_path(path, project)

    layers = (
        [node.layer() for node in group.findLayers()]
        if group
        else project.mapLayers().values()
    )

    for layer in layers:
        if layer_type in {"vect", "xlsx"} and isinstance(layer, QgsVectorLayer):
            if _vector_file_path(layer, project) == target:
                return layer

        elif layer_type == "rast" and isinstance(layer, QgsRasterLayer):
            if _raster_file_path(layer, project) == target:
                return layer

    return None

def seq_read(key, seq_dir, add_to_project=False, group=None, style_folder=None):
    meta = seq_layer(key)
    if not meta:
        raise RuntimeError(f"Couche Sequoia inconnue: {key}")

    layer_type = meta["type"]
    filename = meta["filename"]
    alias = meta["alias"]
    family = (meta.get("family") or "autres").upper()

    seq_dir = Path(seq_dir)
    matches = list(seq_dir.rglob(f"*{filename}"))

    if not matches:
        raise FileNotFoundError(f"Layer '{filename}' not found in '{seq_dir}'")

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple layers found for '{filename}':\n" +
            "\n".join(map(str, matches))
        )

    path = matches[0]
    path_str = str(path)

    project = QgsProject.instance()

    if add_to_project:
        group = group or get_group(family, project=project)

        existing = _find_existing_seq_layer(path, layer_type, group)
        if existing:
            messageLog(f"[SEQ] Déjà chargé : {existing.name()} dans '{group.name()}'")
            raise RuntimeError(f"Couche déjà chargée : {existing.name()}")

    if layer_type in {"vect", "xlsx"}:
        layer = QgsVectorLayer(path_str, alias, "ogr")
    elif layer_type == "rast":
        layer = QgsRasterLayer(path_str, alias)
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
        project.addMapLayer(layer, False)
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
