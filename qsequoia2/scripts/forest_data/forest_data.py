from pathlib import Path
import os, json

from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import QgsProject

from ..utils.messageBar import *
from ..utils.variable import get_project_variable 
from ..utils.seq_config import seq_read
from .forest_get_data import getForestdata

UI_PATH = Path(__file__).parent / "forest_data.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

from pathlib import Path
import importlib

from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import QgsProject, QgsApplication

from ..utils.messageBar import *
from .forest_get_data import getForestdata


UI_PATH = Path(__file__).parent / "forest_data.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


class ForestDataDialog(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.setupUi(self)

        self.project = QgsProject.instance()
        self.metadata = {}

        # Native QGIS refresh icon
        self.btn_update.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.btn_update.setText("")

        # Signals
        self.btn_update.clicked.connect(self.update_view)

    def update_view(self):

        self.project_name = get_project_variable("QS2_project_name")
        self.project_folder = get_project_variable("QS2_project_folder")

        if not self.project_name:
            messageBar(self.iface, "Pas de dossier de projet !", "w", 10)
            return

        parca = seq_read("parca")
        
        print(parca)
    #     self._render_metadata()
 

    # def _render_metadata(self):

    #     html = self._build_html()
    #     self.txt_html.setHtml(html)

    # def _build_html(self) -> str:

    #     template_path = Path(__file__).parent / "html" / "metadata_display.html"
    #     template = template_path.read_text(encoding="utf-8")

    #     forest_name = self.metadata.get("forest_name") or self.project_name

    #     context = {
    #         "forest_name": forest_name,
    #         "departement_str": self.metadata.get("departement_str", ""),
    #         "city_str": self.metadata.get("city_str", ""),
    #         "surface_formatted": self.metadata.get("surface_formatted", ""),
    #         "surface_boisee_ha": self.metadata.get("surface_boisee_ha", ""),
    #         "surface_non_boisee_ha": self.metadata.get("surface_non_boisee_ha", ""),
    #         "owner_str": self.metadata.get("owner_str", ""),
    #     }

    #     return template.format(**context)