from pathlib import Path
import yaml

from qgis.core import QgsVectorTileLayer, QgsProject
from .Qmessage import messageLog
from .layer_tree import get_group
from .plugin_vars import PLUGIN_DIR, CONFIG_CACHE

def get_tms_config_path() -> Path:
    path = PLUGIN_DIR / "config" / "tms.yaml"

    if path.exists():
        return path

    raise RuntimeError("TMS config not found")

def get_tms_config() -> dict:
    if "tms" in CONFIG_CACHE:
        return CONFIG_CACHE["tms"]

    path = get_tms_config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        raise ValueError("Empty config: tms")

    CONFIG_CACHE["tms"] = data
    return data

def tms_layer(key: str) -> dict:
    cfg = get_tms_config()
    return cfg.get(key)

def _build_uri(url: str, style: str | None = None) -> str:
    """
    Build QGIS vector tile URI
    """
    uri = f"type=xyz&url={url}"

    if style:
        uri += f"&styleUrl={style}"

    return uri

def _find_existing_tms(source: str, group=None):
    project = QgsProject.instance()
    layers = [n.layer() for n in group.findLayers()] if group else project.mapLayers().values()

    for layer in layers:
        if isinstance(layer, QgsVectorTileLayer) and layer.source() == source:
            return layer

    return None

def tms_read(key: str, group=None, load_style: bool = True):
    meta = tms_layer(key)
    if not meta:
        raise RuntimeError(f"TMS inconnu: {key}")

    url = meta.get("url")
    name = meta.get("display_name") or key
    style = meta.get("style")
    family = (meta.get("family") or "autres").upper()

    if not url:
        raise RuntimeError(f"URL TMS invalide: {key}")

    project = QgsProject.instance()
    group = group or get_group(family, project=project)

    uri = _build_uri(url, style)

    existing = _find_existing_tms(uri, group)
    if existing:
        messageLog(f"[TMS] Déjà chargé : {existing.name()} dans '{group.name()}'")
        return existing

    opts = QgsVectorTileLayer.LayerOptions(project.transformContext())
    layer = QgsVectorTileLayer(uri, name, opts)

    if not layer.isValid():
        raise RuntimeError(f"TMS layer invalide: {key}")

    if load_style:
        layer.loadDefaultStyle()

    project.addMapLayer(layer, False)
    group.addLayer(layer)

    return layer