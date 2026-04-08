import re
from dataclasses import dataclass
from pathlib import Path

from PyQt5 import uic
from PyQt5.QtWidgets import QButtonGroup, QWidget
from qgis.core import QgsProject

from ..utils.messageBar import messageBar, messageLog
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
        self.type_group = QButtonGroup(self)
        for btn in (self.rb_domaine, self.rb_massif, self.rb_foret, self.rb_bois):
            self.type_group.addButton(btn)

        self.type_group.buttonClicked.connect(self._on_type_changed)

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
            canvas_cfg = self.cfg.get_canvas(project_key)

            ctx = ProjectBuilder(iface=self.iface, project=self.project, seq_id=seq_id, canvas_cfg=canvas_cfg).build()

            if self.cb_composeur.isChecked():
                layout_cfg = self.cfg.get_layout(project_key)
                coeff_cadre = self.dsb_occup.value() / 100
                layout = LayoutBuilder(
                    project=self.project, seq_id = seq_id, layout_cfg = layout_cfg, layers = ctx.layers, coeff_cadre = coeff_cadre
                ).build()

                if not layout:
                    messageBar(self.iface, "Échec de création du layout", "critical", 10)
                    return
                
                self.iface.openLayoutDesigner(layout)

        except Exception as e:
            messageBar(self.iface, str(e), "critical", 10)

    def _on_type_changed(self, button):
        try:
            prefix = button.text()
            base = get_project_variable("QS2_seq_id") or ""
            forest_name = self.format_forest_name(base, prefix)
            self.le_propriete.setText(forest_name)
        except Exception as e:
            messageBar(self.iface, f"Erreur type_changed : {e}", "w", 10)

    def format_forest_name(self, base: str, prefix: str = "") -> str:
        if not base:
            return ""

        base = re.sub(r"^(ST|STE|SAINT)(\w+)", r"\1 \2", base, flags=re.IGNORECASE)

        words = (
            base.lower()
            .replace("_", " ")
            .replace(".", " ")
            .replace("-", " ")
            .split()
        )

        co = {"de", "la", "d", "le"}
        st = {"st", "ste", "saint"}

        formatted = []
        for w in words:
            if w in st:
                formatted.append(w.upper())
            elif w in co:
                formatted.append(w.lower())
            else:
                formatted.append(w.capitalize())

        base = " ".join(formatted)

        if prefix and base:
            if base.lower().endswith("s"):
                connector = " des "
            elif base[0].lower() in "aeiouh":
                connector = " d'"
            else:
                connector = " de "

            return f"{prefix}{connector}{base}"

        return base