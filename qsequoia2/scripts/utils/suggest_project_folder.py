"""
Recherche dans un répertoir général 
de travail un nom de dossier correspondant au nom renseigné dans la barre de recherche de nom de Qsequoia2

Auteur : Alexandre Le Bars - Comité des forêts

D'après les méthodes de Paul Carteron et Matthieu Chevereau
"""

#=======================================
# region import
#=======================================

from pathlib import Path
from .config import get_path
import os

#endregion

#=====================================
# region suggest_project_folder
#=====================================

def suggest_project_folder(project_name, parca_index):
    """
    Retourne tous les dossiers projet contenant une couche PARCA
    dont le nom contient project_name (recherche partielle).
    """

    if not isinstance(project_name, str):
        return None, None

    project_name_lower = project_name.lower()

    matching_folders = []
    matching_names = []

    for item in parca_index:

        if project_name_lower in item["project_name"].lower():

            if item["folder"] not in matching_folders:
                matching_folders.append(item["folder"])
                matching_names.append(item["project_name"])

    if not matching_folders:
        return None, None

    return matching_folders, matching_names

    


# endregion

# en dev appel des fonctions : 

#project_name = "STFRANCHY"
#folders_folder = r"E:\GEO_DEV_SIG\projet"
#style_folder = r"C:\Users\alexl\Desktop\sylviculture et GF\3.cartographie-SIG\Style ALB"
#parent = None

#suggest_project_folder(project_name, folders_folder, style_folder, parent, layout_mode=None)
