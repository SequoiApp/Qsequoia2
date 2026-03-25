from pathlib import Path

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCompleter, QFileDialog

from qsequoia2.scripts.add_data.add_data import AddDataTabWidget
from qsequoia2.scripts.forest_data.forest_data import ForestDataDialog
from qsequoia2.scripts.tools.tools import ToolsDialog
from qsequoia2.scripts.add_on.addon_loader import load_addons
from qsequoia2.scripts.utils.variable import get_global_variable
from qsequoia2.scripts.utils.seq_config import *
from qsequoia2.scripts.utils.messageBar import *

PLUGIN_DIR = Path(__file__).resolve().parent
ICONS_DIR = PLUGIN_DIR / "icons"

UI_PATH = PLUGIN_DIR / "Qsequoia2_dockwidget.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class Qsequoia2DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    projectChanged = pyqtSignal(str, str, str)

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.setupUi(self)

        self._init_ui()
        self._build_project_suggestions()
        self._init_tabs()
        self._load_addons()

        # Connection
        self.btn_select_seq_dir.clicked.connect(self._on_project_selected)
        self.cb_seq_folder.currentIndexChanged.connect(self._on_project_suggested)

    def _init_ui(self):

        qsequoia2_icon = QIcon(str(ICONS_DIR / "Qsequoia2.svg"))
        github_icon = QIcon(str(ICONS_DIR / "github.svg"))

        # button container
        self.btn_sequoia.setIcon(qsequoia2_icon)
        self.btn_reload.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.btn_settings.setIcon(QgsApplication.getThemeIcon("/mActionOptions.svg"))
        self.btn_open_seq_dir.setIcon(QgsApplication.getThemeIcon("/mActionFileOpen.svg"))
        self.btn_issue.setIcon(github_icon)
    
        # Sequoia dir status
        self.lbl_seq_dir_status.clear()
        self.lbl_seq_dir_status.setFixedSize(16, 16)
        self._set_seq_dir_status(False, "Aucun dossier sélectionné")

    # region PROJECT
    def _build_project_suggestions(self):
        """Pure UI"""
        combo = self.cb_seq_folder
        combo.clear()
        combo.setEnabled(True)
        
        suggest_enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))
        messageLog(f"suggest_enabled _build_project_suggestions: {suggest_enabled}")
        if not suggest_enabled:
            combo.setEnabled(False)
            return

        folders = get_global_variable("QS2_project_suggestions") or []

        projects = []
        for folder in folders:
            try:
                projects.extend(find_all_seq_dir(folder))
            except RuntimeError:
                messageBar(self.iface, "Recherche trop étendue...", "c", 10)

        projects = sorted(set(projects), key=lambda p: p.name.lower())

        for p in projects:
            combo.addItem(p.name, str(p))

        self._setup_completer(projects)

        combo.setCurrentIndex(-1)

    def _setup_completer(self, projects):
        combo = self.cb_seq_folder

        if not projects:
            combo.setCompleter(None)
            return

        completer = QCompleter([p.name for p in projects], combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        combo.setCompleter(completer)

    def _on_project_suggested(self, index):
        if index < 0:
            return
        self._select_project(self.cb_seq_folder.itemData(index))

    def _on_project_selected(self):
        seq_dir = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet")
        if not seq_dir:
            return

        combo = self.cb_seq_folder

        combo.blockSignals(True)
        combo.addItem(Path(seq_dir).name, seq_dir)
        combo.setCurrentIndex(combo.count() - 1)
        combo.blockSignals(False)

        self._select_project(seq_dir)
    
    def _select_project(self, seq_dir: str):
        if not seq_dir:
            self._set_seq_dir_status(False, "Aucun dossier sélectionné")
            return

        seq_dirname = Path(seq_dir).name

        try:
            seq_identifier = find_seq_identifier(seq_dir)
        except Exception as e:
            self._set_seq_dir_status(False, "Dossier invalide")
            messageBar(self.iface, f"Dossier invalide : {e}", "c", 10)
            return

        self._set_seq_dir_status(True, "Dossier valide")
        self.projectChanged.emit(seq_dirname, seq_dir, seq_identifier)
        messageBar(self.iface, f"Dossier valide : {seq_dir}", "s", 10)

    def refresh(self):
        self._build_project_suggestions()
        self._select_project(None)

    # endregion

    def _set_seq_dir_status(self, valid: bool, message: str):
        icon = QgsApplication.getThemeIcon("/mIconWarning.svg")
        if valid:
            icon = QgsApplication.getThemeIcon("/mIconSuccess.svg")

        self.lbl_seq_dir_status.setPixmap(icon.pixmap(16, 16))
        self.lbl_seq_dir_status.setToolTip(message)

    def _init_tabs(self):

        def add_tab(widget, icon_name, tooltip):
            icon = QIcon(str(PLUGIN_DIR / "icons" / icon_name))
            self.tabWidget.addTab(widget, icon, "")
            self.tabWidget.setTabToolTip(self.tabWidget.count() - 1, tooltip)

        forest_tab = ForestDataDialog(iface=self.iface,parent=self, )
        add_tab(forest_tab, "forest_data.svg", "Metadonnées sur la propriété")
        
        add_data_tab = AddDataTabWidget(iface=self.iface, parent=self, )
        self.projectChanged.connect(add_data_tab.on_project_changed)
        add_tab(add_data_tab, "add_data.svg", "Ajout de données")

        tools_tab = ToolsDialog(iface=self.iface,parent=self)
        add_tab(tools_tab, "tools.svg", "Outils et fonctions")

        # layout_tab = LayoutDesignerDialog(iface=self.iface,parent=self, )
        # _add_tab(layout_tab, "layout.svg", "Création de carte thématique")

    def _load_addons(self):
        addon_folder = get_global_variable("QS2_addon_folder")
        if addon_folder:
            load_addons(plugin=self, iface=self.iface)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()