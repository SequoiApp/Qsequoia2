from qgis.core import *

# ==========================================================
# LOGGING / MESSAGE
# ==========================================================

def messageBar(iface, text, level="info", duration=5):
    """
    Display a message in the QGIS message bar.

    Parameters
    ----------
    iface : QgisInterface
        The QGIS interface instance (usually `self.iface`).
    text : str
        The message to display.
    level : str
        One of: "i (info)", "s (success)", "w (warning)", "c (critical)".
    duration : int
        Duration in seconds.
    """
    levels = {
        "i": Qgis.Info,
        "s": Qgis.Success,
        "w": Qgis.Warning,
        "c": Qgis.Critical,
    }

    qlevel = levels.get(level, Qgis.Info)

    iface.messageBar().pushMessage(text, level=qlevel, duration=duration)

def messageLog(text, level="info"):
    """        
    Parameters
    ----------
    text : str
        The message to display.
    level : str
        One of: " i (info)", "w (warning)", "c (critical)".
    """
    levels = {
    "i": Qgis.Info,
    "w": Qgis.Warning,
    "c": Qgis.Critical}

    qlevel = levels.get(level, Qgis.Info)

    QgsMessageLog.logMessage(text, "QSEQUOIA2", level=qlevel)