from pathlib import Path
from qgis.core import *

# constantes statiques
PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent
ICONS_DIR = PLUGIN_DIR / "icons"
CACHE_DIR = Path(QgsApplication.qgisSettingsDirPath()) / "qsequoia2"
PROJECT = QgsProject.instance()
CONFIG_CACHE = {}