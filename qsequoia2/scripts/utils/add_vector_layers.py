"""
Module `load_vectors` : fonctions pour charger des couches vecteur dans QGIS
avec application automatique des styles.

Auteur : Alexandre Le Bars - Comité des Forêts, Paul Carteron - Racines experts forestiers associés, Matthieu Chevereau - Caisse des dépôts et consignation
Email : alexlb329@gmail.com
"""
import os
from pathlib import Path
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsMessageLog,
    Qgis)

from .config import get_style


def load_vectors(layer_path, style_folder, project_folder, project_name, group_name=None, parent_group=None,parent=None):
    """
    Charge des couches vecteur dans le projet QGIS.

    La fonction :
    - Crée un groupe si nécessaire
    - Applique le style correspondant (.qml) avant d'ajouter la couche
    - Ajoute la couche au projet et dans le groupe
    - Notifie les erreurs via QgsMessageLog

    Args:
        layer_path (dict): dictionnaire {label: chemin_fichier} des vecteurs à charger
        style_folder (str): dossier contenant les styles (.qml)
        project_folder (str): dossier racine du projet
        project_name (str): nom du projet courant
        group_name (str, optional): nom du groupe QGIS où ajouter les couches
        parent (QWidget, optional): widget parent pour les messages (non utilisé ici)

    Returns:
        list: liste des clés (labels) des vecteurs chargés avec succès

    Auteur : Alexandre Le Bars - Comité des Forêts
    """
    print("load_vectors : layer_path =", layer_path)

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group = None
    loaded_keys = []

    for key, path in layer_path.items():

        layer_name = os.path.splitext(os.path.basename(path))[0]

        layer = QgsVectorLayer(path, layer_name, "ogr")
        print(f"\nload_vectors : adding {layer}")

        if not layer.isValid():
            QgsMessageLog.logMessage(
                f"Failed to load vector '{key}' from {path}",
                "Qsequoia2",
                Qgis.Warning
            )
            continue

        # Créer le groupe si nécessaire

        if group_name is not None :
            group = parent_group

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
        print(f"Layer '{key}' added to project")

        # --- Ajouter dans le groupe si nécessaire ---
        if group:
            group.addLayer(layer)
            print(f"Layer '{key}' added to group '{group_name}'")

        layer.triggerRepaint()
        loaded_keys.append(key)
