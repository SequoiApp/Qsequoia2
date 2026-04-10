from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtCore import QUrl


def open_maps(adress):
    """
    Docstring for open_maps
    
    :param adress: Description
    """
    
    if adress:
        url = QUrl(f"https://www.google.com/maps/search/?api=1&query={adress}")
    else:
        # Si aucune adresse → ouvrir Google Maps normal
        url = QUrl("https://www.google.com/maps")

    QDesktopServices.openUrl(url)
