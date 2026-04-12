import sys
from pathlib import Path
import os

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction, QApplication
from qgis.core import *

from qsequoia2.modules.global_settings.global_settings import GlobalSettingsDialog
from qsequoia2.modules.forest_data.forest_data import ForestDataWidget
from qsequoia2.modules.table_check.table_check import table_check
from qsequoia2.modules.add_data.add_data import AddDataTabWidget
from qsequoia2.modules.utils.disabled_v_external_grass import disabled_v_external_grass
from qsequoia2.modules.utils.seq_config import *
from qsequoia2.modules.utils.Qmessage import *
from qsequoia2.modules.utils.reloader import *
from qsequoia2.modules.utils.variable import *
from qsequoia2.modules.utils.qgz_project import *
from qsequoia2.modules.utils.configure_snapping import configure_snapping
from qsequoia2.modules.utils.plugin_vars import *

from .qsequoia2_dockwidget import Qsequoia2DockWidget

class Qsequoia2:

    def __init__(self, iface):
        self.iface = iface
        self.project = QgsProject.instance()

        # Locale
        locale_value = QSettings().value('locale/userLocale', 'en')
        locale = str(locale_value or "en")[:2]

        locale_path = PLUGIN_DIR / 'i18n' / f'Qsequoia2_{locale}.qm'

        if locale_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(locale_path))
            QCoreApplication.installTranslator(self.translator)

        # UI
        self.actions = []
        self.menu = self.tr("&Qsequoia2")
        self.toolbar = None
        self.dockwidget = None
        self.dlg = None

    def tr(self, message):
        return QCoreApplication.translate('Qsequoia2', message)

    def initGui(self):

        self.toolbar = self.iface.addToolBar("Qsequoia2")
        self.toolbar.setObjectName("Qsequoia2")

        icon_path = ICONS_DIR / "Qsequoia2.svg"

        action = QAction(QIcon(str(icon_path)), self.tr("Qsequoia2"), self.iface.mainWindow())
        action.triggered.connect(self.run)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        # Fetch Rsequoia2 config
        sync_seq_configs()
        disabled_v_external_grass(self.iface)
        configure_snapping()

    def run(self):

        # Handle DockWidget
        ## If already created
        if self.dockwidget:
            if self.dockwidget.isVisible():
                self.dockwidget.close()
            else:

                self.dockwidget.show()
                self.dockwidget.raise_()
            return

        ## Else: create
        self.dockwidget = Qsequoia2DockWidget(iface=self.iface)

        self._connect_dockwidget()

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

    def _connect_dockwidget(self):

        dw = self.dockwidget

        dw.closingPlugin.connect(self._on_closed_plugin)
        dw.projectChanged.connect(self._on_project_changed)

        dw.btn_sequoia.clicked.connect(self._open_sequoia_website)
        dw.btn_settings.clicked.connect(self._open_global_settings)
        dw.btn_reload.clicked.connect(self._reload_plugin)
        dw.btn_open_seq_dir.clicked.connect(self._open_seq_dir)
        dw.btn_issue.clicked.connect(self._open_qsequoia_issue)
    
    def _on_closed_plugin(self):
        """Cleanup when dockwidget is closed"""

        if self.dockwidget:
            try:
                self.dockwidget.closingPlugin.disconnect(self._on_closed_plugin)
            except Exception:
                pass

            self.dockwidget = None

    def _on_project_changed(self, seq_dir, seq_id):

        path = open_seq_project(
            self.project,
            self.iface,
            seq_id,
            seq_dir,
            suffix = "SEQUOIA",
            ask_create=True,
            ask_unsaved=True,
            preserve_qs2_variables=False
        )

        if not path:
            return

        messageLog(f"[PROJECT] Opened project: {path}")
        messageBar(self.iface, f"Projet prêt : {seq_id}", level="success")

        set_project_variable("QS2_seq_dir", seq_dir)
        set_project_variable("QS2_seq_id", seq_id)

        if self.dockwidget:
            self.dockwidget.projectLoaded.emit()

    def _open_global_settings(self):
        """Ouvre la fenêtre de configuration globale du plugin."""
        self.global_settings_dialog = GlobalSettingsDialog(iface=self.iface, plugin=self)
        if self.dockwidget:
            self.global_settings_dialog.settingsUpdated.connect(self.dockwidget.refresh)
        self.global_settings_dialog.show()

    def _reload_plugin(self):
        """Reload plugin (wrapped for clarity)"""
        reloadQS2(self.iface)

    def _open_seq_dir(self):

        seq_dir = get_project_variable("QS2_seq_dir") or ""
        if not seq_dir:
            return

        path = Path(seq_dir)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_sequoia_website(self):
        url = QUrl("https://sequoiapp.github.io/Rsequoia2/index.html")
        QDesktopServices.openUrl(url)
    
    def _open_qsequoia_issue(self):
        url = QUrl("https://github.com/SequoiApp/Qsequoia2/issues")
        QDesktopServices.openUrl(url)
 
    def unload(self):

        # Remove actions
        for action in getattr(self, "actions", []):
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        # Remove toolbar
        if hasattr(self, "toolbar") and self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar = None

        # Remove translator
        if hasattr(self, "translator"):
            QCoreApplication.removeTranslator(self.translator)
