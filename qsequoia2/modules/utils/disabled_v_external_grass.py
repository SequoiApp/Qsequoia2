from qgis.core import *
import processing
from processing.core.ProcessingConfig import ProcessingConfig

from ..utils.Qmessage import *

def disabled_v_external_grass(iface):
    """désactive l'option v.external_grass dans QGIS pour Clean_topology de Rsequoia2"""
    # Récupère le registry des providers
    registry = QgsApplication.processingRegistry()

    # Cherche un provider GRASS
    grass_active = any(provider.name().lower() == "grass" for provider in registry.providers())

    if grass_active:
        ProcessingConfig.setSettingValue("GRASS_USE_VEXTERNAL", False)
        ProcessingConfig.setSettingValue("GRASS_USE_REXTERNAL", False)

        messageLog("L'option v&r.external_grass a été désactivée pour éviter les problèmes de topologie avec Rsequoia2.","i")

    else:
        messageBar(iface, "QSEQUOIA2: Le provider GRASS n'est pas actif. veuillez l'activer dans les extensions pour continuer.","c",10)
