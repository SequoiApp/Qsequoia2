# -*- coding: utf-8 -*-

from pathlib import Path

# QGIS / Qt
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QIcon

# Qsequoia2
from qsequoia2.scripts.data_settings.add_data import AddDataDialog
from qsequoia2.scripts.LayoutDesigner.LayoutDesigner import LayoutDesignerDialog
from qsequoia2.scripts.forest_data.forest_data import ForestDataDialog
from qsequoia2.scripts.tools.tools import ToolsDialog
from qsequoia2.scripts.add_on.addon_loader import load_addons
from qsequoia2.scripts.utils.variable import get_global_variable

PLUGIN_DIR = Path(__file__).resolve().parent
UI_PATH = PLUGIN_DIR / "Qsequoia2_dockwidget.ui"

FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class Qsequoia2DockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.setupUi(self)

        self._init_tabs()
        self._load_addons()

    def _init_tabs(self):

        def _add_tab(widget, icon_name, tooltip):
            icon = QIcon(str(PLUGIN_DIR / "icons" / icon_name))
            self.tabWidget.addTab(widget, icon, "")
            self.tabWidget.setTabToolTip(self.tabWidget.count() - 1, tooltip)

        # forest_tab = ForestDataDialog(iface=self.iface,parent=self, )
        # _add_tab(forest_tab, "forest_data.svg", "Metadata sur la propriété")

        tools_tab = ToolsDialog(iface=self.iface,parent=self, )
        _add_tab(tools_tab, "tools.svg", "Outils et fonctions")

        # layout_tab = LayoutDesignerDialog(iface=self.iface,parent=self, )
        # _add_tab(layout_tab, "layout.svg", "Création de carte thématique")
        
        # add_data_tab = ForestDataDialog(iface=self.iface,parent=self, )
        # _add_tab(add_data_tab, "add_data.svg", "Ajout de données")


    def _load_addons(self):
        addon_folder = get_global_variable("QS2_addon_folder")
        if addon_folder:
            load_addons(plugin=self, iface=self.iface)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()