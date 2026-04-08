from processing.core.ProcessingConfig import ProcessingConfig
from ..utils.Qmessage import *

def disabled_v_external_grass():
    """désactive l'option v.external_grass dans QGIS pour Clean_topology de Rsequoia2"""

    ProcessingConfig.setSettingValue("GRASS_USE_VEXTERNAL", False)
    ProcessingConfig.setSettingValue("GRASS_USE_REXTERNAL", False)

    messageLog("L'option v&r.external_grass a été désactivée pour éviter les problèmes de topologie avec Rsequoia2.","i")


