# -*- coding: utf-8 -*-

from pathlib import Path

# QGIS / Qt
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon

# QSEQUOIA2
from qsequoia2.scripts.data_settings.add_data import AddDataDialog
from qsequoia2.scripts.LayoutDesigner.LayoutDesigner import LayoutDesignerDialog
from qsequoia2.scripts.forest_data.forest_data import ForestDataDialog
from qsequoia2.scripts.tools.tools import ToolsDialog
from qsequoia2.scripts.add_on.addon_loader import load_addons
from qsequoia2.scripts.utils.variable import get_global_variable

PLUGIN_DIR = Path(__file__).resolve().parent
UI_PATH = PLUGIN_DIR / "QSEQUOIA2_dockwidget_base.ui"

FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class QSEQUOIA2DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(
        self,
        iface,
        current_project_name,
        current_style_folder,
        downloads_path,
        current_project_folder,
        parent=None
    ):
        super().__init__(parent)

        self.iface = iface
        self.setupUi(self)

        # store context
        self.project_name = current_project_name
        self.current_style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.current_project_folder = current_project_folder

        self.setWindowIcon(QIcon(str(PLUGIN_DIR / "icon.png")))

        self._init_tabs()
        self._load_addons()

    def _init_tabs(self):

        def make_tab(dialog_cls):
            return dialog_cls(
                current_project_name=self.project_name,
                current_style_folder=self.current_style_folder,
                downloads_path=self.downloads_path,
                current_project_folder=self.current_project_folder,
                iface=self.iface,
                parent=self
            )

        tabs = [
            ("tools.svg", "Outils et fonctions", ToolsDialog),
            ("LayoutDesigner.svg", "Cartographie thématiques", LayoutDesignerDialog),
            ("forest_data.svg", "Metadata sur la propriété", ForestDataDialog),
            ("add_data.svg", "Ajout de données", AddDataDialog),
        ]

        for icon, tooltip, dialog in tabs:
            widget = make_tab(dialog)
            self.tabWidget.addTab(
                widget,
                QIcon(str(PLUGIN_DIR / "icons" / icon)),
                ""
            )
            self.tabWidget.setTabToolTip(self.tabWidget.count() - 1, tooltip)


    def _load_addons(self):
        addon_folder = get_global_variable("QS2_addon_folder")

        if addon_folder:
            load_addons(
                plugin=self,
                current_project_name=self.project_name,
                current_style_folder=self.current_style_folder,
                downloads_path=self.downloads_path,
                current_project_folder=self.current_project_folder,
                iface=self.iface
            )

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()