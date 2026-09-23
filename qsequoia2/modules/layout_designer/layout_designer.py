import re
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTimer
from qgis.core import QgsProject

from ..utils.Qmessage import messageBar, messageLog
from ..utils.variable import get_global_variable, get_project_variable, set_project_variable
from .layout_builder import LayoutBuilder
from .project_builder import ProjectBuilder
from .project_config_loader import ProjectConfigLoader

UI_PATH = Path(__file__).parent / "layout_designer.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

PLUGIN_DIR = Path(__file__).parents[2]
LAYOUT_CONFIG = PLUGIN_DIR / "config" / "layout.yaml"


class LayoutDesignerWidget(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.cfg = ProjectConfigLoader(LAYOUT_CONFIG)      
        self._project_loading = False
        
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
        if self._project_loading:
            return

        seq_id = get_project_variable("QS2_seq_id") or None
        seq_dir = get_project_variable("QS2_seq_dir") or None
        models_dir = get_global_variable("QS2_models_directory") or None
            
        if not seq_dir:
            messageBar(self.iface, "Aucun répertoire sélectionné", "w")
            return
    
        self._project_loading = True
        container = self.parent if self.parent else self
        container.setEnabled(False)

        try:
            project_key = self.combo_project.currentData()
            if not project_key:
                raise RuntimeError("Aucun projet sélectionné")

            canvas_cfg = self.cfg.get_canvas(project_key)
            ctx = ProjectBuilder(
                iface=self.iface,
                project=self.project,
                seq_id=seq_id,
                seq_dir=seq_dir,
                canvas_cfg=canvas_cfg,
                on_project_loaded=self.parent.projectLoaded.emit if self.parent else None,
            ).build()
            
            if ctx is None or ctx.layers is None:
                return None

            messageLog(f"[LAYOUT DESIGNER] context: {ctx}")
            messageLog(f"[PROJECT] setting project variable: {canvas_cfg.key} - {canvas_cfg.alias}")
            set_project_variable("QS2_project_id", canvas_cfg.key)
            set_project_variable("QS2_project_alias", canvas_cfg.alias)
            
            open_composer = self.cb_composeur.isChecked()
            is_sequoia_project = project_key == "sequoia"
            if is_sequoia_project or not open_composer:
                return

            QTimer.singleShot(
                0,
                lambda: self._build_layout(
                    project_key,
                    seq_id,
                    ctx.layers,
                    models_dir,
                ),
            )


        except Exception as e:
            messageBar(self.iface, str(e), "critical", 10)
        finally:
            container.setEnabled(True)
            self._project_loading = False

    def _build_layout(self, project_key, seq_id, layers, models_dir):
        try:
            layout_cfg = self.cfg.get_layout(project_key)
            coeff_cadre = self.dsb_occup.value() / 100
            messageLog(f"[DEBUG] keys layers = {list(layers.keys())}")

            for key, layer in layers.items():
                if layer is None:
                    messageLog(f"[LAYOUT ERROR] layer None -> {key}")

            layout = LayoutBuilder(
                iface=self.iface,
                project=self.project,
                seq_id=seq_id,
                layout_cfg=layout_cfg,
                layers=layers,
                models_dir=models_dir,
                coeff_cadre=coeff_cadre,
            ).build()

            if not layout:
                messageBar(self.iface, "Échec de création du layout", "critical", 10)
                return

            self.iface.openLayoutDesigner(layout)

        except Exception as e:
            messageBar(self.iface, str(e), "critical", 10)

