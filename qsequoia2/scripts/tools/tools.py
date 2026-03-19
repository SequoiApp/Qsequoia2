import importlib
import yaml
from pathlib import Path

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
from qgis.PyQt.QtWidgets import QWidget, QTreeWidget, QVBoxLayout, QTreeWidgetItem
from PyQt5 import uic

from qsequoia2.scripts.tools.python_scripts.go_to_net import go_to_net
from qsequoia2.scripts.utils.variable import get_global_variable

UI_PATH = Path(__file__).parent / "tools.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class ToolsDialog(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.dock = parent

        self.setupUi(self)

        self._init_tree()
        self.treeTOOLS.itemClicked.connect(self.on_item_clicked)

    def _init_tree(self):
        """Build tools tree from YAML"""

        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.treeTOOLS = QTreeWidget()
        self.treeTOOLS.setObjectName("tools")
        self.treeTOOLS.setHeaderLabels(["Outils disponibles"])

        yaml_path = Path(__file__).resolve().parents[2] / "inst" / "qs2_tools.yaml"

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

        layout.addWidget(self.treeTOOLS)
        self.tabWidget.addTab(tab, "OUTILS")


    def on_item_clicked(self, item):

        action = item.data(0, Qt.UserRole)
        if not action:
            return

        parent = item.parent()
        category = parent.text(0) if parent else None

        if category == "Outils web principaux":
            go_to_net(action, self.iface)
            return

        self._call_function(action)

    def _call_function(self, action):

        project_name = get_global_variable("QS2_project_name")
        style_folder = get_global_variable("QS2_styles_directory")

        skip_check = action.get("skip_check", False)

        if not skip_check:

            if not project_name or project_name in ["Nom du projet"]:
                QMessageBox.information(
                    self,
                    "Nom absent",
                    "Merci de renseigner le nom du projet."
                )
                return

            if not style_folder:
                QMessageBox.information(
                    self,
                    "Kartenn",
                    "Pas de dossier de styles sélectionné."
                )
                return

        else:
            project_name = project_name or ""
            style_folder = style_folder or ""

        mod_name = action.get("module")
        func_name = action.get("function")

        if not mod_name or not func_name:
            QMessageBox.warning(
                self,
                "Action incomplète",
                "Cette action n'est pas encore implémentée."
            )
            return

        module = importlib.import_module(mod_name)
        func = getattr(module, func_name)

        func(project_name, style_folder, dockwidget=self, iface=self.iface)
