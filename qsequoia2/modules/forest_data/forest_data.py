
from pathlib import Path
from enum import Enum

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget, QButtonGroup
from PyQt5.QtCore import QTimer
from qgis.core import QgsProject

# Qsequoia2 
from ..utils.variable import set_project_variable, get_project_variable
from ..utils.seq_config import seq_read
from ..utils.Qmessage import messageBar, messageLog
from .forest_metadata_builder import ForestMetadataBuilder
from .update_forest_name import update_forest_name


UI_PATH = Path(__file__).parent / 'forest_data.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class ForestType(Enum):
    DOMAINE = "Domaine"
    MASSIF = "Massif"
    FORET = "Forêt"
    BOIS = "Bois"

class ForestDataWidget(QWidget, FORM_CLASS):
    """Classe principale du module Forestdata de Qsequoia2"""
    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.setupUi(self)

        # --- Radio buttons mapping ---
        self.type = {
            self.rb_domaine: ForestType.DOMAINE,
            self.rb_massif: ForestType.MASSIF,
            self.rb_foret: ForestType.FORET,
            self.rb_bois: ForestType.BOIS,
        }

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.buttonClicked.connect(self._on_rb_clicked)
        for rb in self.type:
            rb.setEnabled(False)
            self.group.addButton(rb)

        # nom de la foret changé manuellement
        self.le_forest_name.editingFinished.connect(self._on_forest_name_entered)

    def on_project_loaded(self):
        seq_dir = get_project_variable("QS2_seq_dir")
        if not seq_dir:
            return

        QTimer.singleShot(0, lambda: self._refresh_metadata(seq_dir))

    def _refresh_metadata(self, seq_dir):
        """Reload data and refresh metadata display"""

        seq_dir = Path(seq_dir)

        # --- PARCA (required) ---
        try:
            parca_layer = seq_read("parca", seq_dir, add_to_project=False)
        except Exception as e:
            self.messageLog(f"[PARCA] Load failed: {e}", level="c")
            messageBar(self.iface, "PARCA layer is required.", level="c")
            return

        # --- UA (optional) ---
        try:
            ua_layer = seq_read("ua", seq_dir, add_to_project=False)
            self._ua_status(True)
        except Exception as e:
            messageLog(f"[UA] Load failed: {e}", "w")
            self._ua_status(False)
            ua_layer = None  # fallback → run without UA

        # --- Enable UI ---
        for rb in self.type:
            rb.setEnabled(True)

        # --- Compute metadata ---
        seq_metadata = self.run_calculation(parca_layer, ua_layer)
        if not seq_metadata:
            return

        self.export_to_project_variables(seq_metadata, seq_dir)
        self.display_base_metadata(seq_metadata)

        self._init_forest_name()
    
    def _init_forest_name(self):
        """Initialize forest name when project changes"""

        messageLog("[FOREST DATA] start _init_forest_name()")
        forest_name = get_project_variable("QS2_forest_name")

        messageLog(f"[FOREST DATA] forest_name: {forest_name}")
        if not forest_name:
            seq_id = get_project_variable("QS2_seq_id")
            prefix = ForestType.FORET.value  # default
            forest_name = update_forest_name(prefix, seq_id)

        self._set_forest_name(forest_name)

    def _set_forest_name(self, forest_name):
        """Single source of truth"""

        messageLog("[FOREST DATA] start _set_forest_name()")
        forest_name = (forest_name or "").strip()
        if not forest_name:
            return

        set_project_variable("QS2_forest_name", forest_name)

        self.le_forest_name.setText(forest_name)

    def _ua_status(self, state):
        if state:
            self.lbl_ua_status.setVisible(False)
        else:
            self.lbl_ua_status.setText("Couche UA non présente ou invalide")
            self.lbl_ua_status.setStyleSheet("color: red;")

    def run_calculation(self, parca_layer, ua_layer):
        if parca_layer is None:
            raise ValueError("PARCA layer is required to compute metadata")

        try:
            get_metadata = ForestMetadataBuilder(parca_layer, ua_layer)
            return get_metadata.build()

        except Exception as e:
            messageBar(self.iface, f"Erreur lors de la construction des metadata : {e}","w")
            return None
        
    def export_to_project_variables(self, seq_metadata, seq_dir):
        """ajoute les données dans les varaibles projets"""

        for key, value in seq_metadata.items():
            if isinstance(value, list):
                for i, item in enumerate(value, start=1):
                    set_project_variable(f"QS2_{key}_{i}", item["name"])
                    set_project_variable(f"QS2_{key}_{i}_surface", item["surface"])
            else:
                set_project_variable(f"QS2_{key}", str(value))

        messageLog(f"-- metadata build pour {seq_dir} --!","i")

    def _format_group(self, data):
        return ", ".join(item.get("name", "") for item in data) 

    def display_base_metadata(self, m):

        self.le_com.setText(self._format_group(m.get("com_name", [])))
        self.le_owner.setText(self._format_group(m.get("owner", [])))
        self.le_dep.setText(self._format_group(m.get("dep_code", [])))
        self.le_reg.setText(self._format_group(m.get("reg_name", [])))

        self.le_surface_total.setText(str(m.get("surface_total", "")))
        self.le_surface_wooded.setText(str(m.get("surface_wooded", "")))
        self.le_surface_unwooded.setText(str(m.get("surface_unwooded", "")))

    def _on_rb_clicked(self, button):
        seq_id = get_project_variable("QS2_seq_id")
        if not seq_id:
            return

        forest_type = self.type.get(button)
        if not forest_type:
            return

        forest_name = update_forest_name(forest_type.value, seq_id)
        self._set_forest_name(forest_name)

    def _on_forest_name_entered(self):
        forest_name = self.le_forest_name.text().strip()
        if not forest_name:
            return

        self._set_forest_name(forest_name)
