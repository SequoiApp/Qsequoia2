from pathlib import Path
import yaml

from qgis.core import QgsVectorTileLayer, QgsProject
from qsequoia2.modules.utils.Qmessage import messageLog
from qsequoia2.modules.utils.seq_config import _CONFIG_CACHE

def get_tms_config_path() -> Path:
    path = Path(__file__).parents[2] / "inst" / "tms.yaml"

    if path.exists():
        return path

    raise RuntimeError("TMS config not found")

def get_tms_config() -> dict:
    if "tms" in _CONFIG_CACHE:
        return _CONFIG_CACHE["tms"]

    path = get_tms_config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        raise ValueError("Empty config: tms")

    _CONFIG_CACHE["tms"] = data
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

def _find_existing_layer(name: str, group=None):
    """
    Avoid duplicate layers using layer name
    """
    project = QgsProject.instance()

    layers = (
        [n.layer() for n in group.findLayers()]
        if group
        else project.mapLayers().values()
    )

    for layer in layers:
        if isinstance(layer, QgsVectorTileLayer) and layer.name() == name:
            return layer

    return None

def tms_read(key: str, group=None, load_style=True):
    """
    Load a vector tile TMS layer from config
    """

    tms = tms_layer(key)
    if not tms:
        raise RuntimeError(f"TMS inconnu: {key}")

    url = tms.get("url")
    name = tms.get("display_name")
    style = tms.get("style")

    if not url:
        raise RuntimeError("URL TMS invalide")

    existing = _find_existing_layer(name, group)
    if existing:
        messageLog(f"[TMS] TMS already {existing.name()} in group: '{group.name() if group else 'root'}'")
        return existing


    uri = _build_uri(url, style)

    opts = QgsVectorTileLayer.LayerOptions(
        QgsProject.instance().transformContext()
    )

    layer = QgsVectorTileLayer(uri, name, opts)

    if not layer.isValid():
        raise RuntimeError(f"TMS layer invalide: {key}")

    if load_style:
        layer.loadDefaultStyle()

    project = QgsProject.instance()
    project.addMapLayer(layer, not bool(group))

    if group:
        group.addLayer(layer)

    return layer