"""
Module new_project

création d'un nouveau dossier de projet vide


Auteur : Alexandre Le Bars - Comité des Forêts

Email : alexlb329@gmail.com

"""

# =====================================
# region Import
# =====================================

# python
import os

# QGIS
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import (QgsProject,QgsCoordinateReferenceSystem)


# endregion

# ====================================
# region create_new_folder
# ====================================


def create_new_folder(project_name, parent_widget=None,log=None,dockwidget=None, iface=None):

    # --- Sélection du dossier source ---

    if not project_name:
        QMessageBox.warning(parent_widget, "Erreur", "Pas de nom de projet")
        return
    
    dossier_source = QFileDialog.getExistingDirectory(parent_widget,"Enregistrer le dossier dans...")

    if not dossier_source:
        return None

    # --- Création du dossier principal ---
    chemin_complet = os.path.join(dossier_source, f"{project_name}_SEQ_SIG")
    os.makedirs(chemin_complet, exist_ok=True)

    # --- Structure des sous-dossiers ---
    structure = [
        "DIVERS",
        "TABLEAUX",
        "MATRICES"]

    for dossier in structure :
        project_folder = os.path.join(chemin_complet, dossier)
        try:
            os.makedirs(project_folder, exist_ok=True)
        except Exception as e:
            QMessageBox.warning( "Erreur", f"Erreur lors de l'acceptation du projet : {e}")
    os.startfile(chemin_complet)
    return chemin_complet


# endregion


# region create_QGIS_project


def ensure_and_load_qgis_project(project, project_folder, project_name, epsg="EPSG:2154"):
    """
    Crée un projet QGIS minimal si absent, vérifie le CRS, met par defaut en EPSG 2154 puis charge le projet.
    Retourne le chemin du projet.
    """

    project = QgsProject.instance()
    project_path = os.path.join(project_folder, f"{project_name}_SEQ_PROJECT.qgz")

    # --- 1. Créer le projet s'il n'existe pas ---
    if not os.path.exists(project_path):
        project.clear()

        # Définir un CRS propre
        crs = QgsCoordinateReferenceSystem(epsg)
        project.setCrs(crs)

        # Marquer le projet comme modifié pour forcer l’écriture
        project.setDirty(True)

        # Écrire le projet vide mais valide
        project.write(project_path)

    # --- 2. Vérifier le CRS du projet existant ---
    # (important pour éviter les projets vides + CRS incohérent)
    temp_project = QgsProject()
    temp_project.read(project_path)
    existing_crs = temp_project.crs()

    if not existing_crs.isValid():
        # Si le CRS est invalide → on le corrige
        crs = QgsCoordinateReferenceSystem(epsg)
        temp_project.setCrs(crs)
        temp_project.write(project_path)

    # --- 3. Charger le projet dans QGIS ---
    project.read(project_path)

    return project_path

    


