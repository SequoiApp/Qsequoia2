from pathlib import Path
import urllib.request
import yaml

from qgis.core import QgsApplication

BASE_URL = "https://raw.githubusercontent.com/SequoiApp/Rsequoia2/main/inst/config"

SEQ_CONFIG_URLS = {
    key: f"{BASE_URL}/{key}.yaml"
    for key in ["seq_fields", "seq_layers", "seq_path", "seq_tables"]
}

CACHE_DIR = Path(QgsApplication.qgisSettingsDirPath()) / "qsequoia2"

def sync_seq_configs(timeout: int = 3) -> None:
    """
    Download latest configs to cache.

    - Silent if offline
    - Safe to call at plugin startup
    """

    CACHE_DIR.mkdir(exist_ok=True)

    for key, url in SEQ_CONFIG_URLS.items():
        path = CACHE_DIR / f"{key}.yaml"

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

    path = CACHE_DIR / f"{name}.yaml"
    if path.exists():
        return path

    raise RuntimeError(
        f"Config '{name}' not found.\n"
        "You need an internet connection for the first plugin use."
    )

def get_seq_config(name: str) -> dict:
    """
    Load YAML config.
    """

    path = get_seq_config_path(name)
    return yaml.safe_load(path.read_text(encoding="utf-8"))