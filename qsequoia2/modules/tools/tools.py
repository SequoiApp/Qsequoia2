from datetime import datetime
from pathlib import Path

from qgis import processing
from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsProviderRegistry,
)

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget, QTreeWidgetItem, QApplication
from PyQt5.QtCore import Qt

from qsequoia2.modules.tools.ua_cleaner import run_clean_ua
from qsequoia2.modules.utils.variable import get_global_variable, get_project_variable
from qsequoia2.modules.utils.Qmessage import messageBar

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

        self.tw_tools.clear()
        self.tw_tools.setHeaderLabels(["UA Tools"])

        clean_item = QTreeWidgetItem(["Nettoyer UA"])
        clean_item.setData(0, Qt.UserRole, self._run_clean_ua)

        self.tw_tools.addTopLevelItem(clean_item)

        self.tw_tools.itemDoubleClicked.connect(self._run)

    def _run(self, item):
        func = item.data(0, Qt.UserRole)
        if callable(func):
            func()

    def _run_clean_ua(self):
        seq_dir = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")

        if not seq_dir:
            raise RuntimeError("Aucune forêt sélectionnée")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        messageBar(self.iface, "Nettoyage UA en cours...", "i", duration=0)

        try:
            backup_path = run_clean_ua(seq_dir, style_folder)

            messageBar(self.iface, f"UA nettoyée. Sauvegarde : {backup_path}", "s")

        except Exception as e:
            messageBar(self.iface, f"Erreur : {str(e)}", "w")

        finally:
            QApplication.restoreOverrideCursor()