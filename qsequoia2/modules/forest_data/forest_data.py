
from pathlib import Path

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
from qgis.core import *

# Qsequoia2 
from .update_forest_name import *
from ..utils.Qmessage import *
from .forest_get_data import *
from ..table_check.data_table import *
from ..utils.variable import *
from ..utils.seq_config import *
from PyQt5.QtCore import QTimer

UI_PATH = Path(__file__).parent / 'forest_data.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class ForestDataTabs(QWidget, FORM_CLASS):
    """Classe principale du module Forestdata de Qsequoia2"""
    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.setupUi(self)

        self.forestType_rb = {
            self.rb_domaine: "Domaine",
            self.rb_massif: "Massif",
            self.rb_foret: "Forêt",
            self.rb_bois: "Bois"
        }

        for rb in self.forestType_rb:
            rb.setEnabled(False)
            self.lbl_type.setEnabled(False)
            rb.toggled.connect(self.on_checkbox_toggled)
        # nom de la foret changé manuellement
        self.seq_id_le.returnPressed.connect(self._on_seq_id_entered)
        self.seq_id_le.editingFinished.connect(self._on_seq_id_entered)

    def on_project_loaded(self, seq_dir, seq_id):
        # attendre que QGIS ait fini de charger les couches
        QTimer.singleShot(300, lambda: self.actu_metadata(seq_dir))

    def actu_metadata(self, seq_dir):
        """relance les fonctions de chargement des data pour actualiser l'affichage"""  

        # métadata build
        seq_dir = Path(seq_dir)
        try: 
            self.parca_layer = seq_read("parca", seq_dir)
            self.ua_layer = seq_read("ua", seq_dir)
        except :
            self._ua_status(state=False)
            return
        
        self._ua_status(state=True)
        
        for rb in self.forestType_rb:
            rb.setEnabled(True)
            self.lbl_type.setEnabled(True)

        # création des métadata 
        seq_metadata = self.run_calculation(seq_dir)
        self.export_to_project_variables(seq_metadata, seq_dir)

        # lecture des metadata
        
        self.display_base_metadata(seq_metadata)
        self.display_forest_name()
        
    def _ua_status(self, state):
        if state:
            self.lbl_ua_status.setVisible(False)
        else:
            self.lbl_ua_status.setText("Couche UA non présente ou invalide")
            self.lbl_ua_status.setStyleSheet("color: red;")

    def run_calculation(self, seq_dir):
        try : 
            get_metadata = getForestdata(self.iface, seq_dir)
            seq_matadata = get_metadata.build(self.ua_layer, self.parca_layer)
            return seq_matadata

        except Exception as e :
            messageBar(self.iface, f"Erreur lors de la construction des metadata : {e}","w",10)
            return {"vide"}
        

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

        self.com_name_le.setText(self._format_group(m.get("com_name", [])))
        self.owner_le.setText(self._format_group(m.get("owner", [])))
        self.dep_code_le.setText(self._format_group(m.get("dep_code", [])))
        self.reg_name_le.setText(self._format_group(m.get("reg_name", [])))

        self.wooded_surface_le.setText(str(m.get("wooded_surface", "")))
        self.no_wooded_surface_le.setText(str(m.get("no_wooded_surface", "")))
        self.total_surface_le.setText(str(m.get("total_surface", "")))


    def display_forest_name(self):

        forest_name = get_project_variable("QS2_forest_name")
        print(f"forest_name: {forest_name}")

        if not forest_name :
            self.seq_id_le.setText("Séléctionnez un Type de propriété")
            return
        
        self.seq_id_le.clear()
        self.seq_id_le.setText(str(forest_name))
        prefix = forest_name.split(" ")[0]
        for cb, label in self.forestType_rb.items():
            cb.setChecked(label == prefix)


    def on_checkbox_toggled(self, checked):

        seq_dir = get_project_variable("QS2_seq_dir")
        seq_id = get_project_variable("QS2_seq_id")

        if not checked:
            return

        if not seq_dir or not seq_id :
            for rb in self.forestType_rb:
                if rb.isChecked():
                    rb.blockSignals(True)
                    rb.setChecked(False)
                    rb.blockSignals(False)
            return
        
        seq_dir = Path(seq_dir)

        if checked:
            sender_rb = self.sender()
            for rb in self.forestType_rb:
                if rb != sender_rb and rb.isChecked():
                    rb.blockSignals(True)
                    rb.setChecked(False)
                    rb.blockSignals(False)

        prefix = next((label for rb, label in self.forestType_rb.items() if rb.isChecked()), "")
        forest_name = update_forest_name(prefix, seq_id)
        self.save_forest_name(forest_name)

    def _on_seq_id_entered(self):
        forest_name = self.seq_id_le.text().strip()
        if not forest_name:
            return
        self.save_forest_name(forest_name)

    def save_forest_name(self, forest_name):

        set_project_variable("QS2_forest_name", forest_name)

        self.seq_id_le.setText(str(forest_name))
