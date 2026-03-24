from pathlib import Path

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject, QgsApplication

# Utils
from ..utils.variable import get_global_variable, set_global_variable
from ..utils.messageBar import messageLog
from ..add_on.addon_creator import addonCreator
from .go_to_maps import open_maps

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

        try:
            self.addon.clicked.disconnect()
        except Exception:
            pass

        self.addon.clicked.connect(self.open_addonCreator)
        self.find_addon_folder.clicked.connect(self.select_addon_folder)

    def load_settings(self):
        styles_dir = get_global_variable("QS2_styles_directory") or ""
        self.stylesInput.setText(styles_dir)

        models_dir = get_global_variable("QS2_models_directory") or ""
        self.modelsInput.setText(models_dir)

        self.userInput.setText(get_global_variable("QS2_user_full_name") or "")
        self.orga.setText(get_global_variable("QS2_organisation") or "")
        self.adress.setText(get_global_variable("QS2_adress_organisation") or "")

        self.open_maps.clicked.connect(lambda: open_maps(self.adress.text()))

        self.open_project.setChecked(bool(get_global_variable("QS2_default_project")))

        suggest_enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))
        self.cb_suggest_enabled.setChecked(suggest_enabled)
        self.list_seq_suggestions.setEnabled(suggest_enabled)

        suggestions = list(get_global_variable("QS2_project_suggestions") or [])
        for folder in suggestions:
            self._add_suggestion(folder)

        addon_folder = get_global_variable("QS2_addon_folder") or ""
        self.addon_folder.setText(addon_folder)
        self.addon.setEnabled(bool(addon_folder))

    def save_settings(self):
        set_global_variable("QS2_styles_directory", self.stylesInput.text())
        set_global_variable("QS2_models_directory", self.modelsInput.text())
        set_global_variable("QS2_user_full_name", self.userInput.text())
        set_global_variable("QS2_adress_organisation", self.adress.text())
        set_global_variable("QS2_organisation", self.orga.text())
        set_global_variable("QS2_default_project", self.open_project.isChecked())
        set_global_variable("QS2_addon_folder", self.addon_folder.text())

        suggest_enabled = self.cb_suggest_enabled.isChecked()
        set_global_variable("QS2_project_suggestions_enabled",suggest_enabled)
        
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

    def generate_addon(self):
        """affiche la fenetre de création des addons"""

        self.addon_folder_path = get_global_variable("QS2_addon_folder")

        if not self.addon_folder_path:
            self.addon_folder_path = None

        self.addon.clicked.connect(self.open_addonCreator)
    
    def select_addon_folder(self):
        """selectionne les dossiers de rangement des addons"""
        addon_path = QgsProject.instance().homePath() or str(Path.home())
        addon_dir = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire des addon", str(addon_path))
        if addon_dir:
            self.addon_folder.setText(addon_dir)
            self.addon_folder_path = addon_dir

    def open_addonCreator(self):
        addon_folder = self.addon_folder.text().strip()
        if not addon_folder:
            QMessageBox.warning(self, "Dossier manquant", "Veuillez sélectionner un dossier d'addons.")
            return

        dialog = addonCreator(iface=self.iface,addon_folder=addon_folder,plugin=self.plugin,parent=self)
        dialog.on_new_addon_clicked()


    



    