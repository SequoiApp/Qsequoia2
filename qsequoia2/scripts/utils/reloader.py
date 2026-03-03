"""

"""
#==================================
# region Import
#==================================

import sys
from time import time
from qgis.PyQt.QtCore import QObject
from qgis.core import Qgis, QgsMessageLog, QgsProject
import qgis.utils

# endregion
#==================================
# region reload
#==================================

def reloadQS2(plugin, plug = "qsequoia2"):
    """
    Reload plugin safely from a module.
    plugin_instance : l'instance du plugin principal (self)
    iface           : QGIS iface (self.iface)
    plug            : nom du plugin à recharger
    """

    project = QgsProject.instance()

    # Enregistrer le projet courant

    if not project.isDirty():
        project.write()
    else:
        # avertir l'utilisateur ou forcer sauvegarde
        project.write()

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
        msg = plugin.tr('<b>{}</b> recharger en {} ms, veuillez fermer puis ouvrir de nouveau le plugin').format(plug,duration)
        plugin.iface.messageBar().pushMessage(msg, Qgis.Success)
        # Actual name of the "Plugins" tab in the message log panel
        # is localized, so we need to find it in QGIS' translations.
        # Don't pass the string value directly to QObject().tr()
        # to prevent local pylupdate from catching it.
        pluginsLogTabSourceName = "Plugins"
        pluginsLogTabName = QObject().tr(pluginsLogTabSourceName)
        QgsMessageLog.logMessage(msg, pluginsLogTabName, level=Qgis.Info)
    

    
