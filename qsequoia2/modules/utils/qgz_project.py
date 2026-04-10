# python
from pathlib import Path

# QGIS
from qgis.core import (QgsProject,QgsCoordinateReferenceSystem)
from qgis.PyQt.QtWidgets import QMessageBox
from qsequoia2.modules.utils.variable import *
from PyQt5.QtWidgets import QFileDialog
from .Qmessage import messageBar

from .plugin_vars import *

def load_project(project, path):
    if not project.read(str(path)):
        raise RuntimeError(f"Failed to load project: {path}")
  
def find_seq_project(seq_id, seq_dir, suffix):
    seq_dir = Path(seq_dir)
    pattern = f"{seq_id}_{suffix}.qgz"

    matches = list(seq_dir.rglob(pattern))

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple QGIS projects found for '{pattern}':\n" +
            "\n".join(map(str, matches))
        )

    return matches[0] if matches else None

def confirm_project_close(project, iface) -> bool:
    """Return False if user cancels"""

    if not project.isDirty():
        return True

    msg = QMessageBox(iface.mainWindow())
    msg.setWindowTitle("Projet non enregistré")
    msg.setText("Le projet courant contient des modifications non enregistrées.")

    save_btn = msg.addButton("Enregistrer", QMessageBox.AcceptRole)
    discard_btn = msg.addButton("Ignorer", QMessageBox.DestructiveRole)
    cancel_btn = msg.addButton("Annuler", QMessageBox.RejectRole)

    msg.exec_()

    if msg.clickedButton() == cancel_btn:
        return False

    if msg.clickedButton() == save_btn:
        if not project.write():
            messageBar(iface, "Échec de l'enregistrement", level="error")
            return False

    return True
  
def new_seq_project(project, iface, seq_id, seq_dir, suffix,
                       datum="EPSG:2154", ask=True):

    if ask:
        create = QMessageBox.question(
            iface.mainWindow(),
            "Projet SEQUOIA",
            f"Aucun projet {seq_id}_{suffix}.qgz trouvé.\nCréer un nouveau projet ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if create == QMessageBox.No:
            return None

    seq_dir = Path(seq_dir)
    project_path = seq_dir / f"{seq_id}_{suffix}.qgz"

    project.clear() 
    project.setCrs(QgsCoordinateReferenceSystem(datum))
    project.setFileName(str(project_path))

    if not project.write():
        raise RuntimeError(f"Failed to create project: {project_path}")

    return project_path

def open_seq_project(
        project,
        iface,
        seq_id,
        seq_dir,
        suffix,
        ask_unsaved=True,
        ask_create=True
    ):
    """
    Full workflow:
    - check unsaved
    - load existing OR create new
    """

    if ask_unsaved and not confirm_project_close(project, iface):
        return None

    path = find_seq_project(seq_id, seq_dir, suffix)
    if path:
        load_project(project, path)
        return path

    return new_seq_project(project, iface, seq_id, seq_dir, suffix, ask=ask_create)