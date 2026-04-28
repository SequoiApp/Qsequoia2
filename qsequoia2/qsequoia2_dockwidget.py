from pathlib import Path
from enum import Enum

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCompleter, QFileDialog, QApplication

from qsequoia2.modules.table_check.ua_checker import ua_checker
from qsequoia2.modules.add_data.add_data import AddDataTabWidget
from qsequoia2.modules.layout_designer.layout_designer import LayoutDesignerWidget
from qsequoia2.modules.forest_data.forest_data import ForestDataWidget
from qsequoia2.modules.tools.tools import ToolsDialog
from qsequoia2.modules.utils.variable import get_global_variable
from qsequoia2.modules.utils.seq_config import *
from qsequoia2.modules.utils.Qmessage import *

PLUGIN_DIR = Path(__file__).resolve().parent
ICONS_DIR = PLUGIN_DIR / "icons"

UI_PATH = PLUGIN_DIR / "Qsequoia2_dockwidget.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class SeqDirState(Enum):
    EMPTY = 0
    INVALID = 1
    VALID = 2

class Qsequoia2DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    projectChanged = pyqtSignal(str, str) #seq_dir, seq_id
    projectLoaded = pyqtSignal()

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
        path = self._project_paths.get(name)
        if path:
            self._select_project(path)

    def _on_project_selected(self):
        seq_dir = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier projet")
        if seq_dir:
            self._select_project(seq_dir)

    def _select_project(self, seq_dir: str):
        self.le_seq_search.clear()
        self.le_seq_search.clearFocus()

        if not seq_dir:
            self._set_seq_dir_status(SeqDirState.EMPTY)
            self.projectChanged.emit(None, None)
            return

        name = Path(seq_dir).name

        try:
            seq_id = find_seq_id(seq_dir)
            state = SeqDirState.VALID
            label = seq_id

        except Exception as e:
            state = SeqDirState.INVALID
            seq_id = None
            label = name
            messageBar(self.iface, str(e), "c", 10)

        self._set_seq_dir_status(state, label)
        messageLog(f"[DEBUG] isDirty before signal emition: {QgsProject.instance().isDirty()}")
        self.projectChanged.emit(seq_dir, seq_id)

        if state == SeqDirState.VALID:
            messageBar(self.iface, f"Dossier valide : {seq_dir}", "s", 10)
    

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
            icon = QgsApplication.getThemeIcon(f"/{icon_name}")
            self.tabWidget.addTab(widget, icon, "")
            self.tabWidget.setTabToolTip(self.tabWidget.count() - 1, tooltip)
            return widget 

        forest_tab = add_tab(ForestDataWidget(iface=self.iface, parent=self), "mActionCalculateField.svg", "Métadonnées")
        ua_check_tab = add_tab(ua_checker(self.iface,parent=self), "mActionZoomToSelected.svg", "Vérification des données")
        add_data_tab = add_tab(AddDataTabWidget(iface=self.iface, parent=self), "mActionAddLayer.svg", "Ajout de données")
        layout_tab = add_tab(LayoutDesignerWidget(iface=self.iface, parent=self), "mActionNewLayout.svg", "Conception de mise en page")
        # tools_tab = add_tab(ToolsDialog(iface=self.iface, parent=self), "processingAlgorithm.svg",  "Outils")


        self.projectChanged.connect(ua_check_tab.on_project_loaded)
        self.projectChanged.connect(add_data_tab.on_project_changed)
        
        self.projectLoaded.connect(forest_tab.on_project_loaded)

    def refresh(self):
        self._update_project_visibility()
        self._build_project_suggestions()