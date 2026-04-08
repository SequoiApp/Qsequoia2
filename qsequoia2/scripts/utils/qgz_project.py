# python
from pathlib import Path

# QGIS
from qgis.core import (QgsProject,QgsCoordinateReferenceSystem)

from qsequoia2.scripts.utils.variable import *

from .plugin_vars import *

def find_qgis_project(seq_dir, seq_dirname):
    seq_dir = Path(seq_dir)
    qgz_files = list(seq_dir.glob("**/*.qgz"))

    for f in qgz_files:
        if seq_dirname in f.name:

            return Load_qgis_project(seq_dir, seq_dirname)

    create_qgis_project(seq_dir, seq_dirname)

    return Load_qgis_project(seq_dir, seq_dirname)

        
# create_QGIS_project

def Load_qgis_project(seq_dir, seq_dirname):
    """load a qgis project from seq_dir"""

    seq_dir = Path(seq_dir)
    project_path = seq_dir / f"{seq_dirname}_SEQUOIA.qgz"
    PROJECT.read(str(project_path))

def create_qgis_project(seq_dir, seq_dirname, datum="EPSG:2154"):
    """create a qgis project to seq_dir with the seq_dirname"""

    seq_dir = Path(seq_dir)
    project_path = seq_dir / f"{seq_dirname}_SEQUOIA.qgz"
    crs = QgsCoordinateReferenceSystem(datum)
    PROJECT.setCrs(crs)
    PROJECT.setDirty(True)
    PROJECT.write(str(project_path))

def close_qgis_project():
    """close the current qgis project if it is a SEQUIOA2 project"""

    seq_dir = get_project_variable("QS2_seq_dir")

    if not seq_dir:
        return
    
    if seq_dir:
        seq_dir = Path(seq_dir)
        PROJECT.instance().write()
        PROJECT.instance().clear()


    


