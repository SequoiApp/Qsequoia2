from pathlib import Path
import yaml

from qgis.core import QgsRasterLayer, QgsProject
from qsequoia2.modules.utils.Qmessage import messageBar, messageLog
from qsequoia2.modules.utils.seq_config import _CONFIG_CACHE

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

from qgis.core import QgsProject, QgsRasterLayer

def wmts_read(key: str, group=None):

    wmts = wmts_layer(key)
    if not wmts:
        raise RuntimeError(f"WMTS inconnu: {key}")

    url = wmts.get("url")
    name = wmts.get("display_name")

    if not url:
        raise RuntimeError("URL WMTS invalide")

    # Check if already exists in group
    if group:
        for node in group.findLayers():
            existing_layer = node.layer()

            if not existing_layer:
                continue

            # WMTS source matching (more robust than ==)
            if existing_layer.source() == url or url in existing_layer.source():
                messageLog(f"WMTS already {existing_layer.name()} in group: '{group.name()}'")
                return existing_layer

    layer = QgsRasterLayer(url, name, "wms")

    if not layer.isValid():
        raise RuntimeError("WMTS layer invalide")

    project = QgsProject.instance()
    project.addMapLayer(layer, not bool(group))

    if group:
        group.addLayer(layer)

    return layer