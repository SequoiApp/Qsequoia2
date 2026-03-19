from pathlib import Path
from collections import defaultdict

from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import QgsProject

from ..utils.messageBar import *
from ..utils.variable import get_project_variable 
from ..utils.seq_config import seq_read, seq_field
from .forest_get_data import getForestdata

UI_PATH = Path(__file__).parent / "forest_data.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

from pathlib import Path

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

        self.btn_update.setIcon(QgsApplication.getThemeIcon("/mActionRefresh.svg"))
        self.btn_update.setText("")

        self.btn_update.clicked.connect(self.update_view)

    def update_view(self):

        self.project_name = get_project_variable("QS2_project_name") or ""
        self.project_folder = get_project_variable("QS2_project_folder") or ""

        if not self.project_name:
            messageBar(self.iface, "Pas de dossier de projet !", "w", 10)
            return

        parca = seq_read("parca", self.project_folder, add_to_project=False)
        f_com_name = seq_field("com_name")["name"]
        f_owner = seq_field("owner")["name"]
        f_surface = seq_field("cad_area")["name"]

        # Aggregation structures
        self.city_surface = defaultdict(float)
        self.owner_surface = defaultdict(float)

        for feat in parca.getFeatures():

            commune = feat[f_com_name]
            owner = feat[f_owner]
            surface = float(feat[f_surface] or 0.0)

            # --- per commune
            self.city_surface[commune] += surface
            self.owner_surface[owner] += surface

        messageLog(f"city_surface:{self.city_surface}")
        messageLog(f"owner_surface:{self.owner_surface}")

        self._render_metadata()

    def _render_metadata(self):

        html = self._build_html()
        self.txt_html.setHtml(html)

    def _build_html(self) -> str:

        template_path = Path(__file__).parent / "html" / "metadata_display.html"
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()

        city_str = ",".join(self.city_surface.keys())
        owner_str = ",".join(self.owner_surface.keys())
        total_surface = sum(self.city_surface.values())

        context = {
            "forest_name": self.project_name,
            "city_str": city_str,
            "owner_str": owner_str,
            "surface_formatted": f"{round(total_surface, 2)} ha",

            # keep others if needed
            "departement_str": "",
            "surface_boisee_ha": "",
            "surface_non_boisee_ha": "",
        }

        return template.format(**context)