from pathlib import Path
from typing import Optional

from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtWidgets import QMessageBox

from qsequoia2.modules.utils.variable import (
    get_qs2_project_variables,
    set_project_variable,
)
from .Qmessage import messageBar, messageLog

def restore_qs2_project_variables(variables: Optional[dict]) -> None:
    """Restore QS2 project variables into the current QGIS project."""
    if not variables:
        return

    for name, value in variables.items():
        set_project_variable(name, value)

def load_project(project, path: Path, variables: Optional[dict] = None) -> None:
    """Load an existing QGIS project and optionally restore QS2 variables."""
    path = Path(path)
    try:
        ok = project.read(str(path))
    except Exception as e:
        messageLog(f"[load_project] Project read crashed {str(e)}", "w")

    if not ok:
        raise RuntimeError(f"Failed to load project: {path}")

    restore_qs2_project_variables(variables)

def find_seq_project(seq_id: str, seq_dir: Path, suffix: str) -> Optional[Path]:
    """Find a unique Sequoia project file matching seq_id and suffix."""
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
    """Ask the user what to do if the current project has unsaved changes."""
    if not project.isDirty():
        return True

    msg = QMessageBox(iface.mainWindow())
    msg.setWindowTitle("Projet non enregistré")
    msg.setText("Le projet courant contient des modifications non enregistrées.")

    save_btn = msg.addButton("Enregistrer", QMessageBox.AcceptRole)
    msg.addButton("Ignorer", QMessageBox.DestructiveRole)
    cancel_btn = msg.addButton("Annuler", QMessageBox.RejectRole)

    msg.exec_()

    if msg.clickedButton() == cancel_btn:
        return False

    if msg.clickedButton() == save_btn and not project.write():
        messageBar(iface, "Échec de l'enregistrement", level="error")
        return False

    return True

def new_seq_project(project,
                    iface,
                    path: Path,
                    datum: str = "EPSG:2154",
                    variables: Optional[dict] = None
                    ) -> Optional[Path]:

    """Create a new QGIS project at the given path."""
    path = Path(path)

    path.parent.mkdir(parents=True, exist_ok=True)

    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem(datum))
    project.setFileName(str(path))
    restore_qs2_project_variables(variables)

    if not project.write():
        raise RuntimeError(f"Failed to create project: {path}")


    return path


def open_seq_project(project,
                     iface,
                     seq_id: str,
                     seq_dir: Path,
                     suffix: str,
                     ask_unsaved: bool = True,
                     preserve_qs2_variables: bool = False,
                     ) -> Optional[Path]:

    """Open an existing Sequoia project or create it if missing."""
    if ask_unsaved and not confirm_project_close(project, iface):
        return None

    seq_dir = Path(seq_dir)
    variables = get_qs2_project_variables() if preserve_qs2_variables else None

    path = find_seq_project(seq_id, seq_dir, suffix)
    if path:
        load_project(project, path, variables)
        return path

    new_project_path = new_seq_project(project, iface, seq_dir / f"{seq_id}_{suffix}.qgz", variables=variables)
    messageBar(iface, f"Project {seq_id}_{suffix}.qgz was created in current seq_dir","s", 15)
    return new_project_path