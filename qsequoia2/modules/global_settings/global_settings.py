from pathlib import Path

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject, QgsApplication

# Utils
from ..utils.variable import get_global_variable, set_global_variable
from ..utils.Qmessage import messageLog
from .go_to_maps import *

FORM_CLASS, _ = uic.loadUiType(
    str(Path(__file__).parent / "global_settings.ui")
)

class GlobalSettingsDialog(QDialog, FORM_CLASS):

    settingsUpdated = pyqtSignal()

    def __init__(self, iface, plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.plugin = plugin
        self.parent = parent
        self.iface = iface

        # Style button
        self.btn_add_project_suggestion.setIcon(QgsApplication.getThemeIcon("/mActionAdd.svg"))
        self.btn_rm_project_suggestion.setIcon(QgsApplication.getThemeIcon("/mActionRemove.svg"))

        # Load settings
        self.load_settings()

        # Connections
        self.buttonBox.accepted.connect(self.save_settings)
        self.stylesButton.clicked.connect(self.select_styles_directory)
        self.modelsButton.clicked.connect(self.select_models_directory)
        self.btn_add_project_suggestion.clicked.connect(self._on_add_suggestion)
        self.btn_rm_project_suggestion.clicked.connect(self._on_rm_suggestion)
        
        self.cb_suggest_enabled.toggled.connect(self.list_seq_suggestions.setEnabled)
        self.cb_suggest_enabled.toggled.connect(self.btn_add_project_suggestion.setEnabled)
        self.cb_suggest_enabled.toggled.connect(self.btn_rm_project_suggestion.setEnabled)


    def load_settings(self):
        styles_dir = get_global_variable("QS2_styles_directory") or ""
        self.stylesInput.setText(styles_dir)

        models_dir = get_global_variable("QS2_models_directory") or ""
        self.modelsInput.setText(models_dir)

        self.userInput.setText(get_global_variable("QS2_user_full_name") or "")
        self.orga.setText(get_global_variable("QS2_organisation") or "")
        self.adress.setText(get_global_variable("QS2_adress_organisation") or "")

        self.open_maps.clicked.connect(lambda: open_maps(self.adress.text()))

        suggest_enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))
        self.cb_suggest_enabled.setChecked(suggest_enabled)
        self.list_seq_suggestions.setEnabled(suggest_enabled)

        messageLog(f"suggest_enabled load: {suggest_enabled}")

        suggestions = list(get_global_variable("QS2_project_suggestions") or [])
        for folder in suggestions:
            self._add_suggestion(folder)

    def save_settings(self):
        set_global_variable("QS2_styles_directory", self.stylesInput.text())
        set_global_variable("QS2_models_directory", self.modelsInput.text())
        set_global_variable("QS2_user_full_name", self.userInput.text())
        set_global_variable("QS2_adress_organisation", self.adress.text())
        set_global_variable("QS2_organisation", self.orga.text())


        suggest_enabled = bool(self.cb_suggest_enabled.isChecked())
        messageLog(f"suggest_enabled before save: {suggest_enabled}")
        set_global_variable("QS2_project_suggestions_enabled", suggest_enabled)
        messageLog(f"suggest_enabled after save: {get_global_variable('QS2_project_suggestions_enabled')}")

        suggestion = self.list_seq_suggestions
        folders = [str(Path(suggestion.item(i).text()).resolve()) for i in range(suggestion.count())]
        set_global_variable("QS2_project_suggestions", folders)

        self.settingsUpdated.emit()

    def select_styles_directory(self):
        base_path = QgsProject.instance().homePath() or str(Path.home())

        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le répertoire de styles",
            base_path
        )

        if not folder:
            return

        folder_path = Path(folder)

        if not any(folder_path.glob("*.qml")):
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Aucun style trouvé",
                f"Le dossier ne contient aucun fichier .qml :\n{folder}"
            )
            return

        self.stylesInput.setText(folder)

    def select_models_directory(self):
        base_path = QgsProject.instance().homePath() or str(Path.home())

        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le répertoire des modèles",
            base_path
        )

        if folder:
            self.modelsInput.setText(folder)

    def _add_suggestion(self, folder_path):
        folder_path = str(Path(folder_path).resolve())

        # Avoid duplicate
        for i in range(self.list_seq_suggestions.count()):
            if self.list_seq_suggestions.item(i).text() == folder_path:
                return

        self.list_seq_suggestions.addItem(folder_path)

    def _on_add_suggestion(self):
        base_path = QgsProject.instance().homePath() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier", base_path, QFileDialog.ShowDirsOnly)

        if not folder:
            return

        self._add_suggestion(folder)

    def _on_rm_suggestion(self):
        for item in self.list_seq_suggestions.selectedItems():
            row = self.list_seq_suggestions.row(item)
            self.list_seq_suggestions.takeItem(row)

    



    