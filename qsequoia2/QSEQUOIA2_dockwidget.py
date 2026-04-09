from pathlib import Path
from enum import Enum

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCompleter, QFileDialog, QApplication

from qsequoia2.scripts.table_check.table_check import table_check
from qsequoia2.scripts.add_data.add_data import AddDataTabWidget
from qsequoia2.scripts.layout_designer.layout_designer import LayoutDesignerWidget
from qsequoia2.scripts.forest_data.forest_data import ForestDataTabs
from qsequoia2.scripts.tools.tools import ToolsDialog
from qsequoia2.scripts.utils.variable import get_global_variable
from qsequoia2.scripts.utils.seq_config import *
from qsequoia2.scripts.utils.Qmessage import *


UI_PATH = PLUGIN_DIR / "Qsequoia2_dockwidget.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class SeqDirState(Enum):
    EMPTY = 0
    INVALID = 1
    VALID = 2


class Qsequoia2DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    projectChanged = pyqtSignal(str, str, str)

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.setupUi(self)

        self._project_paths = {}

        self._init_ui()
        self._connect_signals()
        self._update_project_visibility()
        self._build_project_suggestions()
        self._init_tabs()

    def _init_ui(self):
        icons = {
            self.btn_sequoia: QIcon(str(ICONS_DIR / "Qsequoia2.svg")),
            self.btn_issue: QIcon(str(ICONS_DIR / "github.svg")),
            self.btn_reload: QgsApplication.getThemeIcon("/mActionRefresh.svg"),
            self.btn_settings: QgsApplication.getThemeIcon("/mActionOptions.svg"),
            self.btn_select_seq_dir: QgsApplication.getThemeIcon("/mActionFileOpen.svg"),
            self.btn_open_seq_dir: QgsApplication.getThemeIcon("/mActionLink.svg"),
        }

        for btn, icon in icons.items():
            btn.setIcon(icon)

        self.le_seq_search.setPlaceholderText("Chercher un dossier Sequoia...")

        self.lbl_seq_dir_status.clear()
        self.lbl_seq_dir_status.setFixedSize(16, 16)
        self._set_seq_dir_status(SeqDirState.EMPTY)
        self.btn_update_plugin.setVisible(False)

    def _connect_signals(self):
        self.btn_select_seq_dir.clicked.connect(self._on_project_selected)

    def _update_project_visibility(self):
        enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))
        self.le_seq_search.setVisible(enabled)

    def _build_project_suggestions(self):
        enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))

        if not enabled:
            self._setup_completer([])
            return

        folders = get_global_variable("QS2_project_suggestions") or []

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            projects = self._find_projects(folders)
        finally:
            QApplication.restoreOverrideCursor()

        self._setup_completer(projects)

    def _find_projects(self, folders):
        projects = []

        for folder in folders:
            try:
                projects.extend(find_all_seq_dir(folder))
            except RuntimeError:
                messageBar(self.iface, "Recherche trop étendue...", "c", 10)

        return sorted(set(projects), key=lambda p: p.name.lower())

    def _setup_completer(self, projects):
        if not projects:
            self.le_seq_search.setCompleter(None)
            return

        self._project_paths = {p.name: str(p) for p in projects}

        completer = QCompleter(list(self._project_paths.keys()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)

        self.le_seq_search.setCompleter(completer)
        completer.activated.connect(self._on_project_selected_from_search)

    def _on_project_selected_from_search(self, name):
        seq_dir = self._project_paths.get(name)
        if seq_dir:
            self._select_project(seq_dir)

    def _on_project_selected(self):
        seq_dir = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet")
        if seq_dir:
            self._select_project(seq_dir)

    def _select_project(self, seq_dir: str):
        self.le_seq_search.clear()
        self.le_seq_search.clearFocus()

        if not seq_dir:
            self._set_seq_dir_status(SeqDirState.EMPTY)
            self.projectChanged.emit("", None, None)
            return

        seq_dirname = Path(seq_dir).name

        try:
            seq_identifier = find_seq_identifier(seq_dir)
            state = SeqDirState.VALID
            label = seq_identifier

        except Exception as e:
            state = SeqDirState.INVALID
            seq_identifier = None
            label = seq_dirname
            messageBar(self.iface, str(e), "c", 10)

        self._set_seq_dir_status(state, label)

        self.projectChanged.emit(seq_dir, seq_dirname, seq_identifier)


        if state == SeqDirState.VALID:
            self.forest_tab.actu_metadata(seq_dir)
            self.table_check_tab.actu_Tabledata("Sélectionner une table",seq_dir)
            self.add_data_tab.on_project_changed(seq_dir)
            
            messageBar(self.iface, f"Dossier valide : {seq_dir}", "s", 10)
            self.btn_update_plugin.setVisible(True)


    def _set_seq_dir_status(self, state: SeqDirState, label: str | None = None):
        status_map = {
            SeqDirState.VALID: ("/mIconSuccess.svg", "Dossier valide"),
            SeqDirState.INVALID: ("/mIconWarning.svg", "Dossier invalide"),
            SeqDirState.EMPTY: ("/mIconInfo.svg", "Aucun dossier sélectionné"),
        }

        icon, tooltip = status_map[state]

        self.lbl_seq_dir_status.setPixmap(QgsApplication.getThemeIcon(icon).pixmap(16, 16))
        self.lbl_seq_dir_status.setToolTip(tooltip)

        if state == SeqDirState.EMPTY:
            self.lbl_forest_id.clear()
            self.lbl_forest_id.hide()
        else:
            fm = self.lbl_forest_id.fontMetrics()
            self.lbl_forest_id.setText(fm.elidedText(label, Qt.ElideRight, 150))
            self.lbl_forest_id.setToolTip(label)
            self.lbl_forest_id.show()

    def _init_tabs(self):

        def add_tab(widget, icon_name, tooltip):
            icon = QIcon(str(ICONS_DIR / icon_name))
            self.tabWidget.addTab(widget, icon, "")
            self.tabWidget.setTabToolTip(self.tabWidget.count() - 1, tooltip)
            return widget 

        self.forest_tab = add_tab(ForestDataTabs(iface=self.iface, parent=self), "forest_data.svg", "Métadonnées")
        self.table_check_tab = add_tab(table_check(iface=self.iface, parent=self),"table_check.svg", "Vérification des données")
        self.add_data_tab = add_tab(AddDataTabWidget(iface=self.iface, parent=self), "add_data.svg", "Ajout de données")
        self.layout_tab = add_tab(LayoutDesignerWidget(iface=self.iface, parent=self), "layout.svg", "Conception de mise en page")
        self.tools_tab = add_tab(ToolsDialog(iface=self.iface, parent=self), "tools.svg",  "Outils")

    def refresh(self):
        self._update_project_visibility()
        self._build_project_suggestions()