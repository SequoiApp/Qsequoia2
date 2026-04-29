from pathlib import Path
from sys import prefix

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject, QgsApplication, QgsExpressionContextUtils

# Utils
from ..utils.variable import get_global_variable, set_global_variable
from ..utils.Qmessage import messageBar, messageLog
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
        self.btn_clear_var.setIcon(QgsApplication.getThemeIcon("/mActionReload.svg"))

        # Load settings
        self.load_settings()

        # Connections
        self.buttonBox.accepted.connect(self.save_settings)
        self.btn_styles_directory.clicked.connect(self.select_styles_directory)
        self.btn_models_directory.clicked.connect(self.select_models_directory)
        self.btn_add_project_suggestion.clicked.connect(self._on_add_suggestion)
        self.btn_rm_project_suggestion.clicked.connect(self._on_rm_suggestion)
        self.btn_clear_var.clicked.connect(self._on_clear_global_variables)
        
        self.cb_suggest_enabled.toggled.connect(self.list_seq_suggestions.setEnabled)
        self.cb_suggest_enabled.toggled.connect(self.btn_add_project_suggestion.setEnabled)
        self.cb_suggest_enabled.toggled.connect(self.btn_rm_project_suggestion.setEnabled)

    def load_settings(self):
        styles_dir = get_global_variable("QS2_styles_directory") or ""
        self.le_styles_directory.setText(styles_dir)

        models_dir = get_global_variable("QS2_models_directory") or ""
        self.le_models_directory.setText(models_dir)

        self.le_username.setText(get_global_variable("QS2_username") or "")
        self.le_organization.setText(get_global_variable("QS2_organization") or "")
        self.le_address_street.setText(get_global_variable("QS2_address_street") or "")
        self.le_address_postal_code.setText(get_global_variable("QS2_address_postal_code") or "")
        self.le_address_city.setText(get_global_variable("QS2_address_city") or "")
        self.le_phone.setText(get_global_variable("QS2_phone") or "")
        self.le_email.setText(get_global_variable("QS2_email") or "")
        self.le_website.setText(get_global_variable("QS2_website") or "")
    
        suggest_enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))
        self.cb_suggest_enabled.setChecked(suggest_enabled)
        self.list_seq_suggestions.setEnabled(suggest_enabled)

        messageLog(f"suggest_enabled load: {suggest_enabled}")

        suggestions = list(get_global_variable("QS2_project_suggestions") or [])
        for folder in suggestions:
            self._add_suggestion(folder)

    def save_settings(self):
        set_global_variable("QS2_styles_directory", self.le_styles_directory.text())
        set_global_variable("QS2_models_directory", self.le_models_directory.text())
        set_global_variable("QS2_username", self.le_username.text())
        set_global_variable("QS2_organization", self.le_organization.text())
        set_global_variable("QS2_address_street", self.le_address_street.text())
        set_global_variable("QS2_address_postal_code", self.le_address_postal_code.text())
        set_global_variable("QS2_address_city", self.le_address_city.text())
        set_global_variable("QS2_phone", self.le_phone.text())
        set_global_variable("QS2_email", self.le_email.text())
        set_global_variable("QS2_website", self.le_website.text())

        suggest_enabled = bool(self.cb_suggest_enabled.isChecked())
        set_global_variable("QS2_project_suggestions_enabled", suggest_enabled)

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

        self.le_styles_directory.setText(folder)

    def select_models_directory(self):
        base_path = QgsProject.instance().homePath() or str(Path.home())

        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le répertoire des modèles",
            base_path
        )

        if folder:
            self.le_models_directory.setText(folder)

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

    def _on_clear_global_variables(self):
        prefix = "QS2_"
        max_length = 80
        global_scope = QgsExpressionContextUtils.globalScope()

        qs2_variables = sorted(
            name for name in global_scope.variableNames()
            if name.startswith(prefix)
        )

        def elide_text(text, max_length=max_length):
            text = str(text)
            if len(text) <= max_length:
                return text
            return text[:max_length - 3] + "..."
    
        variables_text = "\n".join(
            f"• {name}: {elide_text(global_scope.variable(name))}"
            for name in qs2_variables
        )

        confirm = QMessageBox.question(
            self.iface.mainWindow(),
            "Réinitialiser les variables",
            (
                "Les variables globales Qsequoia2 suivantes vont être supprimées :\n\n"
                f"{variables_text}\n\n"
                "Voulez-vous continuer ?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirm == QMessageBox.No:
            return []

        for name in qs2_variables:
            QgsExpressionContextUtils.removeGlobalVariable(name)

        messageBar(self.iface, f"{len(qs2_variables)} variable(s) globale(s) Qsequoia2 supprimée(s).", "s")
        return qs2_variables


    