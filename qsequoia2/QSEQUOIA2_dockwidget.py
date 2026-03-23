from pathlib import Path

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QCompleter, QFileDialog
from PyQt5.QtGui import QPixmap

from qsequoia2.scripts.add_data.add_data import AddDataTabWidget
from qsequoia2.scripts.forest_data.forest_data import ForestDataDialog
from qsequoia2.scripts.tools.tools import ToolsDialog
from qsequoia2.scripts.add_on.addon_loader import load_addons
from qsequoia2.scripts.utils.variable import get_global_variable
from qsequoia2.scripts.utils.seq_config import *
from qsequoia2.scripts.utils.messageBar import *

PLUGIN_DIR = Path(__file__).resolve().parent
UI_PATH = PLUGIN_DIR / "Qsequoia2_dockwidget.ui"

FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class Qsequoia2DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    projectChanged = pyqtSignal(str, str, str)
    settingsClicked = pyqtSignal()
    reloadClicked = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.setupUi(self)

        self._init_ui()
        self._init_project_suggestions()
        self._init_project_selection()
        self._init_tabs()
        self._load_addons()

    def _init_ui(self):

        self.cb_seq_folder.setEnabled(True)

        self.setWindowIcon(QIcon(str(PLUGIN_DIR / "icons" / "Qsequoia.png")))
        icon_path = str(PLUGIN_DIR / "icon.png")
             
        pixmap = QPixmap(icon_path)

        self.icon.setPixmap(pixmap)
        self.icon.setScaledContents(True)
        self.icon.setFixedSize(128, 128)


        # Emit signals
        self.btn_settings.clicked.connect(self.settingsClicked)
        self.btn_reload.clicked.connect(self.reloadClicked)

    # region PROJECT
    ## TO-DO extract to specific class
    def _init_project_suggestions(self):

        root = get_global_variable("QS2_project_suggestions_root")
        enabled = bool(get_global_variable("QS2_project_suggestions_enabled"))

        projects = []
        if enabled and root:
            projects = find_seq_dir(root)

        projects = sorted(projects, key=lambda p: p.name.lower())
        project_names = [p.name for p in projects]

        combo = self.cb_seq_folder
        combo.clear()
        combo.setPlaceholderText("Nom du projet")
        combo.setEditable(True)

        for p in projects:
            combo.addItem(p.name, str(p))

        completer = QCompleter(project_names, combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)

        combo.setCompleter(completer)
        combo.setCurrentIndex(-1)

        if not project_names:
            combo.setPlaceholderText("Aucun projet trouvé")

        combo.currentIndexChanged.connect(self._on_project_suggested) 

    def _on_project_suggested(self, index):

        if index < 0:
            return

        combo = self.cb_seq_folder
        seq_dirname = combo.itemText(index)
        seq_dir = combo.itemData(index)

        self._apply_project_selection(seq_dirname, seq_dir)

    def _init_project_selection(self):

        root = get_global_variable("QS2_project_suggestions_root")
        enabled = bool(get_global_variable("QS2_project_suggestions_enabled") or False)

        self._default_project_root = root if enabled and root else ""

        self.btn_select_seq_folder.clicked.connect(self._on_project_selected)

    def _on_project_selected(self):

        seq_dir = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner un dossier projet",
            str(self._default_project_root)
        )

        if not seq_dir:
            return

        combo = self.cb_seq_folder
        seq_dirname = Path(seq_dir).name

        combo.blockSignals(True)
        combo.addItem(seq_dirname, seq_dir)
        combo.setCurrentIndex(combo.count() - 1)
        combo.blockSignals(False)

        self._apply_project_selection(seq_dirname, seq_dir)
    

    def _apply_project_selection(self, seq_dirname, seq_dir):
        if not seq_dir:
            return
        # récupération de l'identifiant de la forêt
        self.seq_identifier = find_seq_identifier(seq_dir)
        self.projectChanged.emit(seq_dirname, seq_dir,self.seq_identifier)
        self.btn_open_seq_dir_2.setEnabled(True)
        self.cb_seq_folder.setEnabled(False)

        messageBar(self.iface, f"Selected directory: {seq_dir}", "s",10)

    # endregion

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