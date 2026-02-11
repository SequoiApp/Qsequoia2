"""
Module `copy_to_gpkg` : fonctions pour copier des couches vecteur passés en listes, les copier dans un geopackage puis les appeler dans QGIS, avec application automatique des styles.


Auteur : Alexandre Le Bars - Comité des Forêts
Email : alexlb329@gmail.com
"""

# ==========================================================
# IMPORTS
# ==========================================================

import os
from pathlib import Path
from qgis.core import (QgsProject,QgsVectorLayer,QgsMessageLog,Qgis)
from .add_vector_layers import load_vectors
import processing

# ==========================================================
# COPY TO GPKG
# ==========================================================

# region copy to gpkg

def copy_to_gpkg(project_key,layer_paths, style_folder, project_folder, project_name, group_name, parent=None):
    """
    Copie les couches dans un geopackage, puis les charge dans QGIS avec enregistrement et application des styles dans la base de données.

    Args:
        project_key (str): Clé du projet dans lequel copier les couches.
        layer_paths (list): Liste de chemins de couches à copier.
        style_folder (str): Chemin du dossier de styles.
        project_folder (str): Chemin du dossier du projet.
        project_name (str): Nom du projet.
        group_name (str): Nom du groupe de couches dans lequel charger les couches.
        parent: Parent widget pour les messages d'erreur.

    Returns:
        None
    """

    # ==========================================================
    # Copier les couches dans un geopackage
    # ==========================================================

    print("Copying layers to GeoPackage...")

    # Verification que les couches sont bien des couches vecteurs

    for layer_path in layer_paths:
        if not layer_path.lower().endswith(('.shp', '.geojson', '.gpkg')):
            QgsMessageLog.logMessage(f"Type de couche non supporté pour la copie : {layer_path}","Qsequoia2",Qgis.Warning)

    # TODO : gérer les rasters et autres types de couches

    # création du dossier de stockage des couches

    vector_root = os.path.join(project_folder, "2_VECTOR")
    project_vector_dir = os.path.join(vector_root, project_key)

    os.makedirs(vector_root, exist_ok=True)
    os.makedirs(project_vector_dir, exist_ok=True)

    gpkg_path = os.path.join(project_vector_dir, f"{project_key}.gpkg")

    # boucle de copie des couches dans un geopackage via l'algorithme "native:package" de processing
    if isinstance(layer_paths, str):
        layer_paths = [layer_paths]
    print("DEBUG layer_paths =", layer_paths)
    for layer_path in layer_paths:

        print(f"Copying layer {layer_path} to {gpkg_path}...")
        try:
            processing.run("native:package", {
                'LAYERS': [layer_path],
                'OUTPUT': gpkg_path,
                'OVERWRITE': False,
                'SAVE_STYLES': True,
                'SAVE_METADATA': True,
                'SELECTED_FEATURES_ONLY': False,
                'EXPORT_RELATED_LAYERS': False,
                'LAYER_NAME': Path(layer_path).stem
            })
        except Exception as e:
            QgsMessageLog.logMessage(f"Erreur copie couche {layer_path} : {e}","Qsequoia2",Qgis.Critical)

    # ==========================================================
    # Charger les couches dans le projet et appliquer + enregistrer les styles
    # ==========================================================

    ## Reprendre ici car le paramètre NAME n'est pas correct voi si on peut lancer add_vector_layer directement sur le gpkg avec une liste de couches à charger, plutôt que couche par couche

    for layer_path in layer_paths:
        # extraire le nom de la couche du chemin pour construire l'URI de chargement
        layer_name = Path(layer_path).stem
        uri = f"{gpkg_path}|layername={layer_name}"

        print("Loading layer:", uri)

        layer = QgsVectorLayer(uri, layer_name, "ogr")

        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
        else:
            print("Layer not found:", layer_name)
        
    # Enregistrer les styles dans le geopackage


    # Ajouter les couches au groupe


# endregion