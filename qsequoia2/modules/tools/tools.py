import importlib
import yaml
from pathlib import Path

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
from qgis.PyQt.QtWidgets import QWidget, QTreeWidget, QVBoxLayout, QTreeWidgetItem
from PyQt5 import uic
from ..utils.Qmessage import *
from qsequoia2.modules.utils.variable import get_global_variable, get_project_variable

UI_PATH = Path(__file__).parent / "tools.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class ToolsDialog(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.dock = parent

        self.setupUi(self)

        self._init_tree()
        
    def _init_tree(self):

        self.treeTOOLS.clear()
        self.treeTOOLS.setHeaderHidden(True)

        yaml_path = Path(__file__).resolve().parents[2] / "config" / "qs2_tools.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

        for category_name, tools in data.items():

            category_item = QTreeWidgetItem([category_name])
            category_item.setExpanded(True)
            self.treeTOOLS.addTopLevelItem(category_item)

            for tool_name, tool_data in tools.items():

                tool_item = QTreeWidgetItem([tool_name])
                tool_item.setData(
                    0,
                    Qt.UserRole,
                    {
                        "type": "tool",
                        "category": category_name,
                        "key": tool_name,
                        **tool_data
                    }
                )

                category_item.addChild(tool_item)

        self.treeTOOLS.itemClicked.connect(self.on_item_clicked)

    def on_item_clicked(self, item):

        action = item.data(0, Qt.UserRole)
        if not action:
            return

        parent = item.parent()
        self._call_function(action)

    def _call_function(self, action):

        seq_dirname = get_project_variable("QS2_seq_dirname")
        seq_dir = get_project_variable("QS2_seq_dir")
        seq_identifier = get_project_variable("QS2_seq_identifier")
        style_folder = get_global_variable("QS2_styles_directory")
        
        skip_check = action.get("skip_check", False)

        if not skip_check:

            if not seq_identifier or not seq_dir :
                messageBar(self.iface, "Aucun projet Sequoia2 ouvert. Veuillez ouvrir un projet Sequoia2 pour utiliser cet outil.","w",10)
                return

            if not style_folder:
                messageBar(self.iface, "Aucun dossier de styles configuré. Veuillez configurer un dossier de styles dans les paramètres globaux pour utiliser cet outil.","w",10)
                return

        else:
            project_name = project_name or ""
            style_folder = style_folder or ""

        mod_name = action.get("module")
        func_name = action.get("function")

        if not mod_name or not func_name:

            messageBar(self.iface, "Cette action n'est pas encore disponible","w",10)
            return

        module = importlib.import_module(mod_name)
        func = getattr(module, func_name)

        func(project_name, style_folder, dockwidget=self, iface=self.iface)
