from pathlib import Path
import yaml

from qsequoia2.modules.utils.seq_config import CONFIG_CACHE
from qsequoia2.modules.utils.plugin_vars import PLUGIN_DIR

def get_alias_config_path() -> Path:
    path = Path(PLUGIN_DIR) / "config" / "alias.yaml"

    if not path.exists():
        raise RuntimeError("Alias config not found")

    return path


def get_alias_config() -> dict[str, str | None]:
    if "alias" in CONFIG_CACHE:
        return CONFIG_CACHE["alias"]

    path = get_alias_config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    if data is None:
        data = {}

    if not isinstance(data, dict):
        raise ValueError("Invalid config: alias.yaml must contain a mapping")

    CONFIG_CACHE["alias"] = data
    return data


def get_alias(key: str) -> str | None:
    cfg = get_alias_config()
    return cfg.get(key) or None