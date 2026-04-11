from pathlib import Path
import yaml

from qgis.core import QgsRasterLayer, QgsProject
from .Qmessage import  messageLog
from .layer_tree import get_group
from .seq_config import _CONFIG_CACHE

def get_wmts_config_path() -> Path:
    path = Path(__file__).parents[2] / "inst" / "wmts.yaml"

    if path.exists():
        return path

    raise RuntimeError("WMTS config not found")

def get_wmts_config() -> dict:
    if "wmts" in _CONFIG_CACHE:
        return _CONFIG_CACHE["wmts"]

    path = get_wmts_config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        raise ValueError("Empty config: wmts")

    _CONFIG_CACHE["wmts"] = data
    return data

def wmts_layer(key):
    wmts_cfg = get_wmts_config()
    return wmts_cfg.get(key)

def _find_existing_wmts(source: str, group=None):
    """Return an already loaded WMTS raster layer matching the same source."""
    project = QgsProject.instance()

    layers = (
        [node.layer() for node in group.findLayers()]
        if group
        else project.mapLayers().values()
    )

    for layer in layers:
        if isinstance(layer, QgsRasterLayer) and layer.source() == source:
            return layer

    return None

def wmts_read(key: str, group=None):
    meta = wmts_layer(key)
    if not meta:
        raise RuntimeError(f"WMTS inconnu: {key}")

    source = meta.get("url")
    name = meta.get("display_name") or key
    family = (meta.get("family") or "autres").upper()

    if not source:
        raise RuntimeError(f"URL WMTS invalide: {key}")

    project = QgsProject.instance()
    group = group or get_group(family, project=project)

    existing = _find_existing_wmts(source, group)
    if existing:
        messageLog(f"[WMTS] Déjà chargé : {existing.name()} dans '{group.name()}'")
        return existing

    layer = QgsRasterLayer(source, name, "wms")
    if not layer.isValid():
        raise RuntimeError(f"WMTS layer invalide: {key}")

    project.addMapLayer(layer, False)
    group.addLayer(layer)

    return layer