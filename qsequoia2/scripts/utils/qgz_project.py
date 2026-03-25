
# =====================================
# Import
# =====================================

# python
from pathlib import Path

# QGIS
from qgis.core import (QgsProject,QgsCoordinateReferenceSystem)

def find_qgis_project(seq_dir, seq_dirname):
    """"""
    seq_dir = Path(seq_dir)
    qgz_file = list(seq_dir.glob("**/*.qgz"))

    for files in qgz_file :
        if seq_dirname in files.name:
            return Load_qgis_project(seq_dir,seq_dirname)
        
        create_qgis_project(seq_dir, seq_dirname)
        
        return Load_qgis_project(seq_dir,seq_dirname)
        
# create_QGIS_project

def Load_qgis_project(seq_dir, seq_dirname):
    """load a qgis project from seq_dir"""
    seq_dir = Path(seq_dir)
    project = project = QgsProject.instance()
    project_path = seq_dir / f"{seq_dirname}_SEQ_PROJECT.qgz"
    project.read(str(project_path))

def create_qgis_project(seq_dir, seq_dirname, datum="EPSG:2154"):
    """create a qgis project to seq_dir with the seq_dirname"""

    seq_dir = Path(seq_dir)
    project = QgsProject.instance()
    project_path = seq_dir / f"{seq_dirname}_SEQ_PROJECT.qgz"
    crs = QgsCoordinateReferenceSystem(datum)
    project.setCrs(crs)
    project.setDirty(True)
    project.write(str(project_path))

    


