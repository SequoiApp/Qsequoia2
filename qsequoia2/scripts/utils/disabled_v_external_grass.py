from processing.core.ProcessingConfig import ProcessingConfig

def disabled_v_external_grass():
    """désactive l'option v.external_grass dans QGIS pour Clean_topology de Rsequoia2"""

    ProcessingConfig.setSettingValue("GRASS_USE_VEXTERNAL", False)
    ProcessingConfig.setSettingValue("GRASS_USE_REXTERNAL", False)
