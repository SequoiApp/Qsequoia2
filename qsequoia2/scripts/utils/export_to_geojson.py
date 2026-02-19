"""
Module `export to geojson` : fonctions pour exporter des couches vecteur passés en listes vers GeoJSON.


Auteur : Alexandre Le Bars - Comité des Forêts
Email : alexlb329@gmail.com
"""

# ==========================================================
# IMPORTS
# ==========================================================

import os
from pathlib import Path
from qgis.core import (QgsProject,QgsVectorLayer,QgsMessageLog,Qgis)

from qsequoia2.scripts.utils import layers
from .add_vector_layers import load_vectors
import processing

# ==========================================================
# COPY TO GPKG
# ==========================================================

# region copy to gpkg
def export_to_geojson(layer_paths, project_vector_dir, layer_name_override=None,):
    """
    Export une ou plusieurs couches en GeoJSON.
    - layer_paths : liste de chemins sources (SHP, GPKG, etc.)
    - project_vector_dir : dossier de sortie déjà créé
    - layer_name_override : nom forcé pour la couche GeoJSON
    """
    print("test")
    print(f"export_to_geojson : layer_paths = {layer_paths}, project_vector_dir = {project_vector_dir}, layer_name_override = {layer_name_override}")
    for layer_path in layer_paths:
        # Nom du layer
        layer_name = layer_name_override or os.path.splitext(os.path.basename(layer_path))[0]

        # Nom de la carte actuel

        project_key = os.path.splitext(os.path.basename(project_vector_dir))[0].upper()

        # Chemin GeoJSON de sortie
        gjs_path = os.path.join(project_vector_dir, f"{project_key}_{layer_name}.geojson")

        print(f"Copying layer {layer_path} to {gjs_path}...")

        # retirer la couche de QGIS 

        for lyr in list(QgsProject.instance().mapLayers().values()):
            if lyr.source() == gjs_path:
                QgsProject.instance().removeMapLayer(lyr.id())

        # Exporter via processing
        processing.run(
            "native:savefeatures",
            {
                "INPUT": layer_path,
                "OUTPUT": gjs_path,
                "LAYER_NAME": layer_name,
                "DATASOURCE_OPTIONS": "",
                "LAYER_OPTIONS": "",
                "ACTION_ON_EXISTING_FILE": 0
            }
        )

        print(f"GeoJSON created: {gjs_path}")
