"""
extract_files.py
================

Détection et extraction automatique des ZIPs pour le plugin QSEQUOIA2.

- Surveille les fichiers ZIP arrivant dans le dossier de téléchargements.
- Affiche un bandeau dans QGIS pour demander à l'utilisateur s'il souhaite
  extraire les fichiers.
- Si accepté, les fichiers sont extraits dans un dossier choisi et ajoutés
  dans QGIS (vecteurs et rasters).

Auteur : Alexandre Le Bars - Comité des Forêts
Projet : Kartenn
Année : 2026
Email : alexlb329@gmail.com
"""

import zipfile, os

from qgis.PyQt.QtWidgets import QFileDialog, QPushButton, QWidget
from qgis.core import Qgis
from qgis.utils import iface


from .add_vector_layers import load_vectors
from .add_raster_layers import load_rasters


def show_add_banner(project_folder, downloads_path, project_name, style_folder, _zip_path, dockwidget):
    """
    Affiche le bandeau dans QGIS pour proposer à l'utilisateur
    d'extraire un ZIP détecté.

    :param project_folder: chemin du projet QGIS
    :param downloads_path: dossier de téléchargements surveillé
    :param project_name: nom du projet courant
    :param style_folder: dossier des styles
    :param _zip_path: chemin du ZIP détecté
    :param dockwidget: référence au dockwidget QGIS (peut être None)
    """

    bar = iface.messageBar()


    message = bar.createMessage(
        "[Watchdog] ",
        f"Ajout détecté dans : {downloads_path}. Que voulez-vous faire ?"
    )


    btn_ok = QPushButton("Ranger les couches")

    def on_click():

        try:
            real_extract_files(downloads_path, project_name, style_folder, project_folder,_zip_path,dockwidget)
        except Exception as e:
            print("Erreur dans real_extract_files :", e)
        bar.popWidget(message)

    btn_ok.clicked.connect(on_click)
    message.layout().addWidget(btn_ok)
    bar.pushWidget(message, Qgis.Success)

    # Supprime le message
    #bar.popWidget(message)



def real_extract_files(downloads_path, project_name, style_folder, project_folder, _zip_path, dockwidget=None):
    """
    Extrait les fichiers d'un ZIP dans un dossier choisi par l'utilisateur
    et les charge dans QGIS.

    :param downloads_path: dossier de téléchargements
    :param project_name: nom du projet courant
    :param style_folder: dossier des styles
    :param project_folder: chemin du projet QGIS
    :param _zip_path: chemin du ZIP à traiter
    :param dockwidget: dockwidget QGIS pour parent des dialogues
    """
    # --- Extraction dans dossier ---
    def_folder = QFileDialog.getExistingDirectory(dockwidget, "Sélectionner le dossier de stockage des fichiers")
    if not def_folder:
        print("Aucun dossier sélectionné.")
        return

    extr_folder = os.path.abspath(def_folder)
    print(f"\nExtract_files indique => Rangement vers : {extr_folder}")

    # Fichiers avant extraction (récursif, chemins complets)
    before_files_all = set()
    for root, dirs, files in os.walk(extr_folder):
        for f in files:
            before_files_all.add(os.path.join(root, f))

    # --- Extraction du zip ---
    with zipfile.ZipFile(_zip_path, 'r') as z:
        z.extractall(extr_folder)

    # Fichiers après extraction (récursif, chemins complets)
    after_files_all = set()
    for root, dirs, files in os.walk(extr_folder):
        for f in files:
            after_files_all.add(os.path.join(root, f))

    # Nouveaux fichiers extraits uniquement
    new_files_path = list(after_files_all - before_files_all)
    print("Nouveaux fichiers extraits :", new_files_path)

    # Détection des extensions
    vector_ext = {".shp", ".geojson", ".gpkg", ".kml", ".las", ".laz"}
    raster_ext = {".tiff", ".tif", ".png"}

    def get_extension(path):
        return os.path.splitext(path)[1].lower()

    # --- Message dans la barre QGIS ---
    bar = iface.messageBar()
    message = bar.createMessage("[Extract_files] ", f"Fichiers déplacés vers : {extr_folder}")

    # Bouton pour ouvrir le dossier
    btn_ok = QPushButton("Ouvrir ici")

    def on_click():

        # Vecteurs
        vector_files = [f for f in new_files_path if get_extension(f) in vector_ext]
        if vector_files:
            print("\nVecteurs détectés :", vector_files)
            layer_path = {os.path.splitext(os.path.basename(f))[0]: f for f in vector_files}
            load_vectors(layer_path, style_folder, project_folder, project_name, group_name=None, parent=dockwidget)

        # Rasters
        raster_files = [f for f in new_files_path if get_extension(f) in raster_ext]
        if raster_files:
            print("\nRasters détectés :", raster_files)
            layer_path = {os.path.splitext(os.path.basename(f))[0]: f for f in raster_files}
            load_rasters(layer_path, project_folder, project_name, style_folder, group_name=None, parent=dockwidget)

        # Supprime le message
        bar.popWidget(message)

    
    # Appel du boutton

    btn_ok._callback = on_click

    btn_ok.clicked.connect(btn_ok._callback)

    # Ajouter le bouton
    message.layout().addWidget(btn_ok)

    # Afficher
    bar.pushWidget(message, Qgis.Success)

    #Supprime le ZIP initial

    os.remove(_zip_path)



