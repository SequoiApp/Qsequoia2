from pathlib import Path

from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem, QWidget

from qsequoia2.modules.tools.plt_merger import PltMerger
from qsequoia2.modules.tools.ua_cleaner import run_clean_ua
from qsequoia2.modules.utils.Qmessage import messageBar
from qsequoia2.modules.utils.variable import (
    get_global_variable,
    get_project_variable,
)


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
        self.tw_tools.setHeaderLabels(["Outils"])

        tools = {
            "Nettoyer UA": self._run_clean_ua,
            "Fusionner les rasters PLT": self._open_plt_merge,
        }

        for label, callback in tools.items():
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, callback)
            self.tw_tools.addTopLevelItem(item)

        self.tw_tools.itemDoubleClicked.connect(self._run)

    def _run(self, item, _column=0):
        callback = item.data(0, Qt.UserRole)

        if callable(callback):
            callback()

    def _get_seq_dir(self):
        seq_dir = get_project_variable("QS2_seq_dir")

        if not seq_dir:
            messageBar(
                self.iface,
                "Aucune forêt sélectionnée.",
                "w",
            )
            return None

        return Path(seq_dir)

    def _open_plt_merge(self):
        seq_dir = self._get_seq_dir()

        if seq_dir:
            PltMerger(iface=self.iface,seq_dir=seq_dir).open_dialog()

    def _run_clean_ua(self):
        seq_dir = self._get_seq_dir()

        if not seq_dir:
            return

        style_folder = get_global_variable("QS2_styles_directory")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        messageBar(
            self.iface,
            "Nettoyage UA en cours...",
            "i",
            duration=0,
        )

        try:
            backup_path = run_clean_ua(seq_dir, style_folder)

            messageBar(
                self.iface,
                f"UA nettoyée. Sauvegarde : {backup_path}",
                "s",
            )

        except Exception as error:
            messageBar(
                self.iface,
                f"Erreur : {error}",
                "w",
            )

        finally:
            QApplication.restoreOverrideCursor()