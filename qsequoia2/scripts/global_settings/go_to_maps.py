from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtCore import QUrl


def open_maps(adress):
    """
    Open google map with the adress of your organisation
    
    :param adress: adress of your organisation
    """
    
    if adress:
        url = QUrl(f"https://www.google.com/maps/search/?api=1&query={adress}")
    else:
        # Si aucune adresse → ouvrir Google Maps normal
        url = QUrl("https://www.google.com/maps")

    QDesktopServices.openUrl(url)
