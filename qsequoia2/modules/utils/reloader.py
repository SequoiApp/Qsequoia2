"""

"""
#==================================
# region Import
#==================================

# Python
import sys
from time import time

# QGIS
from qgis.PyQt.QtCore import QObject
from qgis.core import Qgis, QgsMessageLog, QgsProject
from .Qmessage import messageBar, messageLog, messageBox
import qgis.utils
from .plugin_vars import *

# endregion
#==================================
# region reload
#==================================
PROJECT = QgsProject.instance()

def reloadQS2(plugin, plug = "qsequoia2"):
    """
    Reload plugin safely from a module.
    plugin_instance : l'instance du plugin principal (self)
    iface           : QGIS iface (self.iface)
    plug            : nom du plugin à recharger
    """
    # Si plugin est l'interface QGIS → OK
    if hasattr(plugin, "messageBar"):
        iface = plugin

    # Sinon plugin est ton plugin → on récupère self.iface
    elif hasattr(plugin, "iface"):
        iface = plugin.iface


    # Enregistrer le projet courant

    if not PROJECT.isDirty():
        PROJECT.write()
    else:
        # avertir l'utilisateur ou forcer sauvegarde
        PROJECT.write()

    # Forcer la fermeture et ouvrture d'une nouvelle fenêtre Qsequoia2
    if hasattr(plugin, "main_window") and plugin.main_window:
        plugin.main_window.setParent(None)
        plugin.main_window.close()
        plugin.main_window.deleteLater()
        plugin.main_window = None


    # lancement du Timer

    startTime = time()

    # Try to initially load the selected plugin if not loaded yet
    if plug not in qgis.utils.plugins:
        qgis.utils.loadPlugin(plug)
        qgis.utils.startPlugin(plug)
        qgis.utils.updateAvailablePlugins()

    qgis.utils.unloadPlugin(plug)

    # Remove submodules left by qgis.utils.unloadPlugin
    # NOTE Since QGIS 3.4.8, imported submodules are unloaded automagically
    # by qgis.utils.unloadPlugin. However, parent packages that weren't
    # directly imported, are not handled.
    for key in list(sys.modules.keys()):
        if plug in key:
            if hasattr(sys.modules[key], 'qCleanupResources'):
                sys.modules[key].qCleanupResources()
            del sys.modules[key]

    qgis.utils.loadPlugin(plug)
    pluginStarted = qgis.utils.startPlugin(plug)

    endTime = time()

    if pluginStarted:
        duration = int(round((endTime - startTime) * 1000))
        messageBox(iface, "IMPORTANT !", f'{plug}\n rechargé en {duration} ms, veuillez fermer puis ouvrir de nouveau l interface du plugin', "i")

    

    
