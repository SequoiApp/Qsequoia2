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

from qsequoia2.scripts.utils import layers
from .add_vector_layers import load_vectors

from qgis.core import (QgsProject, QgsVectorLayer, QgsVectorFileWriter, QgsMessageLog, Qgis)


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


    # Normaliser en liste
    if isinstance(layer_paths, (str, Path)):
        layer_paths = [layer_paths]

    gpkg_path = Path(project_folder) / "2_VECTOR" / project_key / f"{project_key}.gpkg"
    gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    gpkg_posix = gpkg_path.as_posix()

    for src in layer_paths:
        src = Path(src)
        v = QgsVectorLayer(src.as_posix(), src.stem, "ogr")
        if not v.isValid():
            QgsMessageLog.logMessage(f"Couche invalide: {src}", "Qsequoia2", Qgis.Critical)
            continue

        print(f"test{layer_paths} et {src} et {v} et {gpkg_posix}")
        

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName  = src.stem
        # Remplace la table homonyme si elle existe (n’efface pas le fichier)
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

        # -- Appel compatible multi-versions (2/3/1 valeurs) --
        res = QgsVectorFileWriter.writeAsVectorFormatV3(
            v, gpkg_posix, QgsProject.instance().transformContext(), opts
        )
        # Normaliser 'err' quel que soit le format renvoyé
        if isinstance(res, tuple):
            err = res[0]  # (error, ...) 2 ou 3 éléments
        else:
            err = res

        if err != QgsVectorFileWriter.NoError:
            QgsMessageLog.logMessage(f"Erreur export '{src.stem}' (code={err})", "Qsequoia2", Qgis.Critical)
            continue

        # Charger + styles
        dest = f"{gpkg_posix}|layername={src.stem}"
        load_vectors({src.stem: dest}, style_folder, project_folder, project_name, group_name, parent)

# endregion