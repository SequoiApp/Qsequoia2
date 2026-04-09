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

from qgis.PyQt.QtWidgets import QFileDialog, QPushButton
from qgis.core import Qgis
from qgis.utils import iface

def show_add_banner(project_folder, downloads_path, project_name, style_folder, _zip_path, dockwidget):
    """
    Affiche le bandeau dans QGIS pour proposer à l'utilisateur
    d'extraire un ZIP détecté.
    """

    bar = iface.messageBar()

    message = bar.createMessage("[Watchdog] ",f"Ajout détecté dans : {downloads_path}. Que voulez-vous faire ?")

    btn_ok = QPushButton("Ranger les couches dans le dossier de projet ?")
    btn_ok2 = QPushButton("Ranger les couches ailleurs")

    def on_click(in_folder):
        try:
            real_extract_files(project_folder, _zip_path, in_folder, dockwidget)
        except Exception as e:
            print("Erreur dans real_extract_files :", e)

        bar.popWidget(message)

    btn_ok.clicked.connect(lambda: on_click(True))
    btn_ok2.clicked.connect(lambda: on_click(False))

    message.layout().addWidget(btn_ok)
    message.layout().addWidget(btn_ok2)

    bar.pushWidget(message, Qgis.Success)


def real_extract_files(project_folder, _zip_path, in_folder, dockwidget=None):
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
    if in_folder == False:
        def_folder = QFileDialog.getExistingDirectory(dockwidget, "Sélectionner le dossier de stockage des fichiers")
        if not def_folder:
            print("Aucun dossier sélectionné.")
        return
    else : 
        def_folder = project_folder

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


    # --- Message dans la barre QGIS ---
    bar = iface.messageBar()
    message = bar.createMessage("[Extract_files] ", f"Fichiers déplacés vers : {extr_folder}")

    # Afficher
    bar.pushWidget(message, Qgis.Success)

    #Supprime le ZIP initial

    os.remove(_zip_path)



