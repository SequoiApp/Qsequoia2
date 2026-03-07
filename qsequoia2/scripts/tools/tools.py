"""Modules outils"""


# ==========================================================================
# region import
# ==========================================================================

# python 

import os, importlib, yaml, json


# QGIS

from PyQt5.QtWidgets import QDialog, QMessageBox, QFileDialog
from PyQt5.QtCore import Qt
from qgis.PyQt.QtWidgets import QWidget, QTreeWidget, QVBoxLayout, QTreeWidgetItem
from PyQt5 import uic

# QSEQUOIA2

from qsequoia2.scripts.tools.python_scripts.go_to_net import go_to_net
from qsequoia2.scripts.tools.python_scripts.unknow_function import unknown_function

# UI
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'tools.ui'))


# endregion
# ==========================================================================
# region ToolsDialog
# ==========================================================================

class ToolsDialog(QWidget, FORM_CLASS):
    def __init__(self, current_project_name, current_style_folder, downloads_path, current_project_folder, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.current_project_name = current_project_name
        self.current_style_folder = current_style_folder
        self.downloads_path = downloads_path
        self.current_project_folder = current_project_folder

        self.setupUi(self)
        self.add_tree_tools()
        self.dock = parent

        # Connexion des signaux pour appel des fonctions
        self.treeTOOLS.itemClicked.connect(self.on_item_clicked)

    # ------------------------------------------------------------------------
    # Création de l'arbre de fonction depuis la table fonction en yaml
    # ------------------------------------------------------------------------

    def add_tree_tools(self):
        """
        Crée et remplit l'onglet OUTILS à partir du YAML qseq_functions.yaml
        """

        # Widget onglet
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # TreeWidget
        self.treeTOOLS = QTreeWidget()
        self.treeTOOLS.setObjectName("tools")
        self.treeTOOLS.setHeaderLabels(["Outils disponibles"])

        # Lecture du YAML
        script_dir = os.path.dirname(__file__)
        yaml_path = os.path.join(script_dir, "..", "..", "inst", "qseq_functions.yaml")

        with open(yaml_path, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

            for category_name, tools in data.items():
                # Création de la catégorie
                category_item = QTreeWidgetItem([category_name])
                category_item.setExpanded(True)
                self.treeTOOLS.addTopLevelItem(category_item)

                # dict des fonctions
                for tool_name, tool_data in tools.items():
                    tool_item = QTreeWidgetItem([tool_name])

                    # stocker les infos pour usage ultérieur
                    tool_item.setData(0, Qt.UserRole,
                                      {"type": "tool",
                                       "category": category_name,  # catégorie parent
                                       "key": tool_name,            # clé YAML de l'outil
                                       **tool_data                 # function/module/skip_check/url...
                                       })

                    category_item.addChild(tool_item)

        # Ajout au layout
        layout.addWidget(self.treeTOOLS)

        # Ajout à l’onglet
        self.tabWidget.addTab(tab, "OUTILS")


    #-------------------------------------------------------------------------
    # Import des fonctions externes et appel en fonction de l'item cliqué
    #-------------------------------------------------------------------------

    def on_item_clicked(self, item, column):
        """
        Slot appelé lors d’un clic sur un item d’un QTreeWidget.

        Args:
            item (QTreeWidgetItem): l’élément cliqué
            column (int): la colonne cliquée
        """
        action = item.data(0, Qt.ItemDataRole.UserRole)

        # Si pas de data
        if action is None:
            return
        parent = item.parent()
        category = parent.text(0) if parent else None

        if category == "Outils web principaux":
            go_to_net(action, self.iface)
            return

        self.call_functions(action, category)

    def call_functions(self, action, category):
        project_name = getattr(self, "current_project_name", "DefaultProject")
        style_folder = getattr(self, "current_style_folder", None)

        skip_check = action.get("skip_check", False)
        if not skip_check:

            if not project_name or project_name in ["Nom du projet","DefaultProject"]:

                QMessageBox.information(self,"Nom absent","Merci de renseigner le nom du projet.")
                return

            if not style_folder:
                QMessageBox.information(self,"Kartenn","Pas de dossier de styles sélectionné.")
                return
        else:
            project_name = project_name or ""
            style_folder = style_folder or ""

        mod_name = action.get("module")
        func_name = action.get("function")

        if not mod_name or not func_name:
            QMessageBox.warning(self,"Action incomplète","Cette action n'est pas encore implémentée.")
            return
        
        module = importlib.import_module(mod_name)

        func = getattr(module, func_name)

        func(project_name, style_folder, dockwidget=self, iface=self.iface)



