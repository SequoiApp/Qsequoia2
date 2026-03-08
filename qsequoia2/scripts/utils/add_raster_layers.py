"""
Module `load_rasters` : fonctions pour charger des rasters dans QGIS avec style automatique.

Auteur : Alexandre Le Bars - Comité des Forêts, Paul Carteron - Racines experts forestiers associés, Matthieu Chevereau - Caisse des dépôts et consignation
Email : alexlb329@gmail.com
"""

# ==================================================================================
# Import
# ==================================================================================

# python
import os

# QGIS

from qgis.core import (QgsProject,QgsRasterLayer,QgsMessageLog,Qgis)
from qgis.core import QgsRasterLayer

# Qsequoia2

from .config import get_style

# ==================================================================================
# load_rasters
# ==================================================================================


def load_rasters(layer_path, project_folder, project_name, style_folder, group_name=None, parent=None):
    """
    Charge des couches raster dans le projet QGIS.

    La fonction :
    - Crée un groupe si nécessaire
    - Applique le style correspondant (.qml) avant d'ajouter la couche
    - Ajoute la couche au projet et dans le groupe
    - Notifie les erreurs via QgsMessageLog

    Args:
        layer_path (dict): dictionnaire {label: chemin_fichier} des rasters à charger
        project_folder (str): dossier racine du projet
        project_name (str): nom du projet courant
        style_folder (str): dossier contenant les styles (.qml)
        group_name (str, optional): nom du groupe QGIS où ajouter les couches
        parent (QWidget, optional): widget parent pour les messages (non utilisé ici)

    Returns:
        list: liste des clés (labels) des rasters chargés avec succès

    """
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group = None
    loaded_keys = []

    for key, path in layer_path.items():

        layer_name = os.path.splitext(os.path.basename(path))[0]

        # --- Charger le raster correctement ---
        layer = QgsRasterLayer(path, layer_name, "gdal")
        print(f"\nload_rasters : adding {layer}")

        if not layer.isValid():
            QgsMessageLog.logMessage(
                f"Failed to load raster '{key}' from {path}",
                "Qsequoia2",
                Qgis.Warning
            )
            continue

        # --- Créer le groupe si nécessaire ---
        if group_name and group is None:
            group = root.findGroup(group_name) or root.addGroup(group_name)



        # --- Charger le style AVANT d'ajouter la couche ---
        style = get_style(layer_path, style_folder)

        if style:
            try:
                res, msg = layer.loadNamedStyle(str(style))
                if not res:
                    QgsMessageLog.logMessage(f"Impossible d'appliquer le style '{key}': {msg}", "Qsequoia2", Qgis.Warning)
                else:
                    # Appliquer immédiatement le style chargé
                    layer.triggerRepaint()
            except Exception as e:
                QgsMessageLog.logMessage(f"Erreur lors de l'application du style '{key}': {e}", "Qsequoia2", Qgis.Warning)

        # --- Ajouter la couche au projet ---
        project.addMapLayer(layer, not bool(group))

        # --- Ajouter dans le groupe si nécessaire ---
        if group:
            group.addLayer(layer)

        layer.triggerRepaint()
        loaded_keys.append(key)