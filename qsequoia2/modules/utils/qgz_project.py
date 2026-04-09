# python
from pathlib import Path

# QGIS
from qgis.core import (QgsProject,QgsCoordinateReferenceSystem)
from qgis.PyQt.QtWidgets import QMessageBox
from qsequoia2.modules.utils.variable import *
from PyQt5.QtWidgets import QFileDialog

from .plugin_vars import *
PROJECT = QgsProject.instance()

def find_qgis_project(seq_dir, seq_id):
    seq_dir = Path(seq_dir)
    qgz_files = list(seq_dir.glob("**/*.qgz"))

    for f in qgz_files:
        if seq_id in f.name:

            return Load_qgis_project(seq_dir, seq_id)

    create_qgis_project(seq_dir, seq_id)

    return Load_qgis_project(seq_dir, seq_id)

        
# create_QGIS_project

def Load_qgis_project(seq_dir, seq_id):
    """load a qgis project from seq_dir"""

    seq_dir = Path(seq_dir)
    project_path = seq_dir / f"{seq_id}_SEQUOIA.qgz"
    PROJECT.read(str(project_path))

def create_qgis_project(seq_dir, seq_id, datum="EPSG:2154"):
    """create a qgis project to seq_dir with the seq_dirname"""

    seq_dir = Path(seq_dir)
    project_path = seq_dir / f"{seq_id}_SEQUOIA.qgz"
    crs = QgsCoordinateReferenceSystem(datum)
    PROJECT.setCrs(crs)
    PROJECT.setDirty(True)
    PROJECT.write(str(project_path))

def close_qgis_project(iface):
    """close the current qgis project if it is a SEQUIOA2 project"""

    seq_dir = get_project_variable("QS2_seq_dir")

    if not seq_dir:
        return
    
    if seq_dir:
        seq_dir = Path(seq_dir)
        write = QMessageBox.question(
            iface.mainWindow(),
            "Projet courant",
            f"Enregistrer le projet courant ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No)

        if write == QMessageBox.No:
            return
        if write == QMessageBox.Yes:
            PROJECT.instance().write()
            
        PROJECT.instance().clear()


    


