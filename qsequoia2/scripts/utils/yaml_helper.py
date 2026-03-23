import yaml
from pathlib import Path
from qgis.core import *

_CACHE_DIR = Path(QgsApplication.qgisSettingsDirPath()) / "qsequoia2"

def yaml_loader(name : str, level: str) -> dict:
    """
    Load a YAML file in config cache and return data at the specified level.

    Args:
        name (str): name of the YAML file in cache.
        level (str): Top-level key in the YAML to extract.

    Returns:
        dict: Data under the specified level, or {} if missing.
    """
    path = Path(_CACHE_DIR) / name

    if not path.exists():
        return
    
    with open(path, "r", encoding="utf-8") as f:
        bigdata = yaml.safe_load(f) or {}
    return bigdata.get(level, {})



def yaml_creator(name: str, data_to_save: dict):
    """
    Create or overwrite a YAML file in _CACHE_DIR.

    Args:
        name (str): name of the YAML file (e.g., "forest_metadata.yaml")
        data_to_save (dict): data to save in YAML

    Returns:
        Path: path to the created YAML file
    """
    path = Path(_CACHE_DIR) / name

    if not path.exists():
        return
    
    # Écriture du YAML (création ou remplacement)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            data_to_save,
            f,
            sort_keys=False,
            allow_unicode=True
        )


