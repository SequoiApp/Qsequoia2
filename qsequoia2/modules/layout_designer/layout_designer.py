import re
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from qgis.core import QgsProject

from ..utils.Qmessage import messageBar, messageLog
from ..utils.variable import get_project_variable
from .layout_builder import LayoutBuilder
from .project_builder import ProjectBuilder
from .project_config_loader import ProjectConfigLoader


UI_PATH = Path(__file__).parent / "layout_designer.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

PLUGIN_DIR = Path(__file__).parents[2]
LAYOUT_CONFIG = PLUGIN_DIR / "inst" / "layout.yaml"


class LayoutDesignerWidget(QWidget, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.cfg = ProjectConfigLoader(LAYOUT_CONFIG)

        self.setupUi(self)
        self._init_ui()

    def _init_ui(self):

        self.combo_project.clear()
        for key, alias in self.cfg.get_projects():
            self.combo_project.addItem(alias, key)

        self.combo_project.setCurrentIndex(0)

        self.cb_composeur.toggled.connect(self.dsb_occup.setEnabled)
        self.dsb_occup.setEnabled(self.cb_composeur.isChecked())

        self.btn_run.clicked.connect(self._accept)

    def _accept(self):
        try:
            project_key = self.combo_project.currentData()
            if not project_key:
                raise RuntimeError("Aucun projet sélectionné")

            seq_id = get_project_variable("QS2_seq_id") or None
            seq_dir = get_project_variable("QS2_seq_dir") or None
            canvas_cfg = self.cfg.get_canvas(project_key)

            ctx = ProjectBuilder(iface=self.iface, project=self.project, seq_id=seq_id, seq_dir=seq_dir, canvas_cfg=canvas_cfg).build()
            messageLog(f"[LAYOUT DESIGNER] context: {ctx}")

            if self.cb_composeur.isChecked():
                layout_cfg = self.cfg.get_layout(project_key)
                coeff_cadre = self.dsb_occup.value() / 100
                layout = LayoutBuilder(
                    iface = self.iface, project=self.project, seq_id = seq_id, layout_cfg = layout_cfg, layers = ctx.layers, coeff_cadre = coeff_cadre
                ).build()

                if not layout:
                    messageBar(self.iface, "Échec de création du layout", "critical", 10)
                    return
                
                self.iface.openLayoutDesigner(layout)

        except Exception as e:
            messageBar(self.iface, str(e), "critical", 10)