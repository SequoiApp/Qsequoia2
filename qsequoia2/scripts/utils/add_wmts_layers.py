"""
Module `load_wmts` : fonctions pour charger des couches WMTS dans QGIS.

Auteur : Alexandre Le Bars - Comité des Forêts
        Paul Carteron - Racines experts forestiers associés
        Matthieu Chevereau - Caisse des dépôts et consignation
Email : alexlb329@gmail.com

Fonctionnalité :
- Charger des couches WMTS depuis le fichier de configuration wmts.yaml
- Ajouter les couches au projet QGIS
- Créer un groupe optionnel pour les couches
"""

from qgis.core import (QgsProject, QgsRasterLayer,QgsMessageLog,Qgis)

from .config import get_wmts



def load_wmts(label, group_name = None):
    """
    Charge des couches WMTS dans le projet QGIS.

    La fonction :
    - Cherche la configuration WMTS dans `wmts.yaml` via get_wmts
    - Crée un groupe si nécessaire
    - Ajoute les couches au projet et dans le groupe
    - Ignore les couches déjà chargées
    - Notifie les erreurs via QgsMessageLog

    Args:
        label (list[str]): liste des clés des couches WMTS à charger
        group_name (str, optional): nom du groupe QGIS où ajouter les couches

    """
    project = QgsProject.instance()
    root = project.layerTreeRoot()

    # find or create the target group
    group = None
    if group_name:
        group = root.findGroup(group_name) or root.addGroup(group_name)

    for key in label:
        display_name, url = get_wmts(key)
        if project.mapLayersByName(display_name):
            QgsMessageLog.logMessage(f"Layer '{display_name}' already loaded, skipping.", "Qsequoia2", Qgis.Info)
            print(f"Layer '{display_name}' already loaded, skipping.")
            continue

        layer = QgsRasterLayer(str(url), display_name, "wms")

        if not layer.isValid():
            QgsMessageLog.logMessage(f"Failed to load WMTS '{key}' from {url}", "Qsequoia2", Qgis.Warning)
            continue

        # add to project, optionally hide it from the legend
        project.addMapLayer(layer, not bool(group))

        if group:
            group.addLayer(layer)