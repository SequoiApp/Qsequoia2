
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
    """Classe principale du module ForestData de Qsequoia2."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.setupUi(self)

        self.forest_types = {
            self.rb_domaine: ForestType.DOMAINE,
            self.rb_massif: ForestType.MASSIF,
            self.rb_foret: ForestType.FORET,
            self.rb_bois: ForestType.BOIS,
        }

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.buttonClicked.connect(self._on_rb_clicked)

        for rb in self.forest_types:
            rb.setEnabled(False)
            self.group.addButton(rb)

        self.le_forest_name.editingFinished.connect(self._on_forest_name_entered)

    def on_project_loaded(self):
        seq_dir = get_project_variable("QS2_seq_dir")
        if seq_dir:
            QTimer.singleShot(0, lambda: self._refresh_metadata(seq_dir))

    def _refresh_metadata(self, seq_dir):
        seq_dir = Path(seq_dir)

        parca_layer = self._load_parca(seq_dir)
        if parca_layer is None:
            return

        ua_layer = self._load_ua(seq_dir)

        try:
            metadata = ForestMetadataBuilder(parca_layer, ua_layer).build()
        except Exception as e:
            messageBar(
                self.iface,
                f"Erreur lors de la construction des métadonnées : {e}",
                level="w",
            )
            return

        self._enable_forest_types()
        self._export_to_project_variables(metadata, seq_dir)
        self._display_base_metadata(metadata)
        self._init_forest_name()

    def _load_parca(self, seq_dir):
        try:
            return seq_read("parca", seq_dir, add_to_project=False)
        except Exception as e:
            messageLog(f"[PARCA] Load failed: {e}", "c")
            messageBar(self.iface, "La couche PARCA est requise.", level="c")
            return None

    def _load_ua(self, seq_dir):
        try:
            return seq_read("ua", seq_dir, add_to_project=False)
        except Exception as e:
            messageLog(f"[UA] Load failed: {e}", "w")
            return None

    def _enable_forest_types(self):
        for rb in self.forest_types:
            rb.setEnabled(True)

    def _init_forest_name(self):
        forest_name = get_project_variable("QS2_forest_name")

        if not forest_name:
            seq_id = get_project_variable("QS2_seq_id")
            if not seq_id:
                return

            forest_name = update_forest_name(ForestType.FORET.value, seq_id)

        self._set_forest_name(forest_name)

    def _set_forest_name(self, forest_name):
        forest_name = (forest_name or "").strip()
        if not forest_name:
            return

        set_project_variable("QS2_forest_name", forest_name)
        self.le_forest_name.setText(forest_name)

    def _export_to_project_variables(self, metadata, seq_dir):
        # Clear optional UA variable first.
        # If UA exists, metadata["surface_soumise"] will overwrite it.
        set_project_variable("QS2_surface_soumise", "")

        for key, value in metadata.items():
            if isinstance(value, list):
                for i, item in enumerate(value, start=1):
                    set_project_variable(f"QS2_{key}_{i}", item["name"])
                    set_project_variable(f"QS2_{key}_{i}_surface", item["surface"])
            else:
                set_project_variable(f"QS2_{key}", str(value))

        messageLog(f"-- metadata build pour {seq_dir} --!", "i")

    def _format_group(self, data):
        return ", ".join(item.get("name", "") for item in data)

    def _display_base_metadata(self, metadata):
        self.le_com.setText(self._format_group(metadata.get("com_name", [])))
        self.le_owner.setText(self._format_group(metadata.get("owner", [])))
        self.le_dep.setText(self._format_group(metadata.get("dep_code", [])))
        self.le_reg.setText(self._format_group(metadata.get("reg_name", [])))

        self.le_surface_total.setText(str(metadata.get("surface_total", "")))

    def _on_rb_clicked(self, button):
        seq_id = get_project_variable("QS2_seq_id")
        forest_type = self.forest_types.get(button)

        if not seq_id or not forest_type:
            return

        forest_name = update_forest_name(forest_type.value, seq_id)
        self._set_forest_name(forest_name)

    def _on_forest_name_entered(self):
        self._set_forest_name(self.le_forest_name.text())