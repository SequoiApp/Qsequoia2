

import os,re
import json
from pathlib import Path


from qgis.PyQt.QtWidgets import QMessageBox, QButtonGroup
from qgis.core import QgsProject
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import  Qt
from PyQt5 import uic

from .layout_loader import LayoutLoader
from .layout_builder import LayoutBuilder
from ..utils.messageBar import messageBar
from ..utils.variable import get_project_variable

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
        self.cfg = LayoutLoader(LAYOUT_CONFIG)
        self.setupUi(self)

        # button
        self.type_group = QButtonGroup(self)

        self.type_group.addButton(self.rb_domaine)
        self.type_group.addButton(self.rb_massif)
        self.type_group.addButton(self.rb_foret)
        self.type_group.addButton(self.rb_bois)

        self.type_group.buttonClicked.connect(self._on_type_changed)

        # project
        self.combo_project.clear()
        for key, alias in self.cfg.get_projects():
            self.combo_project.addItem(alias, key)

        self.combo_project.currentIndexChanged.connect(self._on_project_changed)
        self.combo_project.setCurrentIndex(0)

        # param
        self.cb_composeur.toggled.connect(self.dsb_occup.setEnabled)
        self.dsb_occup.setEnabled(self.cb_composeur.isChecked())

        # run
        self.btn_run.clicked.connect(self._accept)

    def _on_project_changed(self):
        project_key = self.combo_project.currentData()
        if not project_key:
            return
        
        self._update_scale(project_key)

    def _on_type_changed(self, button):

        try:
            prefix = button.text()
            base = get_project_variable("QS2_seq_identifier") or ""
            forest_name = self.format_forest_name(base, prefix)
            self.le_propriete.setText(forest_name)

        except Exception as e:
            messageBar(self.iface, f"Erreur type_changed : {e}", "w", 10)

    def _update_scale(self, project_key):
        try:
            canvas = self.cfg.get_canvas(project_key)
            if canvas.scale:
                self.sb_scale.setValue(canvas.scale)

        except Exception as e:
            messageBar(self.iface, f"Erreur update_scale : {e}", "w", 10)

    def format_forest_name(self, base: str, prefix: str = "") -> str:
        if not base:
            return ""

        # 1. Separate ST/STE/SAINT if glued
        base = re.sub(r"^(ST|STE|SAINT)(\w+)", r"\1 \2", base, flags=re.IGNORECASE)

        # 2. Normalize
        words = (
            base.lower()
            .replace("_", " ")
            .replace(".", " ")
            .replace("-", " ")
            .split()
        )

        co = {"de", "la", "d", "le"}
        st = {"st", "ste", "saint"}

        # 3. Capitalization rules
        formatted = []
        for w in words:
            if w in st:
                formatted.append(w.upper())  # ST, STE, SAINT
            elif w in co:
                formatted.append(w.lower())  # de, la, etc.
            else:
                formatted.append(w.capitalize())

        base = " ".join(formatted)

        # 4. Prefix logic
        if prefix and base:
            if base.lower().endswith("s"):
                connector = " des "
            elif base[0].lower() in "aeiouh":
                connector = " d'"
            else:
                connector = " de "

            return f"{prefix}{connector}{base}"

        return base
    
    def _accept(self):

        project_key = self.combo_project.currentData()
        if not project_key:
            return
        
        seq_id = get_project_variable("QS2_seq_identifier") or None
        if not project_key:
            return
        
        builder = LayoutBuilder(self.iface, seq_id, self.cfg, project_key)
        builder._build()

        # # ================================
        # # 4. Ouvrir et construire la mise en page 
        # # ================================
        # if self.cb_composeur.isChecked():

        #     canvas_cfg = self.config.get_project_canvas(project_key)
        #     layout_cfg = self.config.get_project_layout(project_key)

        #     # créer le service Layout
        #     layout_service = LayoutService(
        #         project=QgsProject.instance(),
        #         project_key = project_key,
        #         project_name=self.current_project_name,
        #         style_folder=self.current_style_folder,
        #         downloads_path=self.downloads_path,
        #         project_folder=self.current_project_folder,
        #         iface=self.iface)
            

        #     # Calcul format + orientation
        #     info = layout_service.compute_layout_info(
        #         scale=canvas_cfg.scale,
        #         coeff_cadre=self.dsb_occup.value() / 100)

        #     # Import layout et conserver la référence
        #     self.current_layout = layout_service.import_layout(project_key=project_key, fmt=info.paper_format, orient=info.orientation)

        #     # Ajouter au layout manager
        #     lm = QgsProject.instance().layoutManager()

        #     # éviter les collisions de nom, je le garde pour le dev je met une condition pour éviter erreur python si le projet existe déja
        #     if self.current_layout is not None:
        #         existing = lm.layoutByName(self.current_layout.name())
        #         if existing:
        #             lm.removeLayout(existing)
        #     else :
        #         return

        #     lm.addLayout(self.current_layout)

        #     # Configurer le layout
        #     layout_service.configure_layout(
        #         layout=self.current_layout,
        #         theme=layout_cfg.theme,
        #         scale=canvas_cfg.scale,
        #         legends=layout_cfg.legends
        #     )

        #     # Ouvrir le designer
        #     self.iface.openLayoutDesigner(self.current_layout)


        #     # mettre l'échelle de QGIS à la version du projet
        #     self.iface.mapCanvas().zoomScale(canvas_cfg.scale)

        #     #Mettre la loupe à 100%
        #     self.iface.mapCanvas().setMapTool(self.iface.mapCanvas().mapTool())


        # #except Exception as e:
        
        #     #messageBar(self.iface, f"Echec de la mise en page {e}","critical", 10)





