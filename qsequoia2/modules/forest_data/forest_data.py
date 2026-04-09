
# ==========================================================================
# import
# ==========================================================================

# python 

from pathlib import Path
import json

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import *
from PyQt5.QtWidgets import QTableWidgetItem, QHeaderView, QButtonGroup
from PyQt5.QtCore import Qt

# Qsequoia2 
from .update_forest_name import *
from ..utils.Qmessage import *
from .forest_get_data import *
from ..table_check.data_table import *
from ..utils.variable import *
from ..utils.seq_config import *

UI_PATH = Path(__file__).parent / 'forest_data.ui'
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

# ==========================================================================
# region initalisation
# ==========================================================================

class ForestDataTabs(QDialog, FORM_CLASS):
    """Classe principale du module Forestdata de Qsequoia2"""
    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.parent = parent
        self.project = QgsProject.instance()
        self.setupUi(self)

        # checkboxes de type de forêt
        self.forestType_rb = {
            self.rb_domaine: "Domaine",
            self.rb_massif: "Massif",
            self.rb_foret: "Forêt",
            self.rb_bois: "Bois"
        }

        for rb in self.forestType_rb:
            rb.setVisible(False)
            self.lbl_type.setVisible(False)
            rb.toggled.connect(self.on_checkbox_toggled)

    # endregion
    # ================================================
    # region Metadonnées
    # ================================================


    def actu_metadata(self, seq_dir, seq_dirname=None, seq_identifier= None):
        """relance les fonctions de chargement des data pour actualiser l'affichage"""  

        # métadata build

        seq_dir = Path(seq_dir)
        self.parca_layer = seq_read("parca", seq_dir)
        self.ua_layer = seq_read("ua", seq_dir)

        for rb in self.forestType_rb:
            rb.setVisible(True)
            self.lbl_type.setVisible(True)

        # création des métadata 
        seq_metadata = self.run_calculation(seq_dir)
        self.export_to_project_variables(seq_metadata, seq_dir)

        # lecture des metadata
        self.get_base_metadata()
        self.display_base_metadata()


    def run_calculation(self, seq_dir):
        try : 
            seq_metadata = getForestdata(self.iface, seq_dir)

            return seq_metadata.build(self.ua_layer, self.parca_layer)

        except Exception as e :
            messageBar(self.iface, f"Erreur lors de la construction des metadata : {e}","w",10)
            return {"vide"}
        
        
    def export_to_project_variables(self, seq_metadata, seq_dir):
        """ajoute les données dans les varaibles projets"""

        for key, value in seq_metadata.items():
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            set_project_variable(f"QS2_{key}", value)

        messageLog(f"-- metadata build pour {seq_dir} --!","i")


    # ================================================
    # Metadata Lecture et affichage
    # ================================================

    def get_base_metadata(self):
        """Récupère les metadata"""

        def load_var(key):
            val = get_project_variable(f"QS2_{key}")
            try:
                return json.loads(val)
            except (TypeError, json.JSONDecodeError):
                return val

        self.city_list = load_var("city_list")
        self.city_str = load_var("city_str")
        self.owner_list = load_var("owner_list")
        self.owner_str = load_var("owner_str")
        self.dep_list = load_var("departement_list")
        self.dep_str = load_var("departement_str")
        self.wooded_surface = load_var("wooded_surface")
        self.no_wooded_surface = load_var("no_wooded_surface")
        self.total_surface = load_var("total_surface")
        self.surface_formatted = load_var("surface_formatted")
        self.forest_name = load_var("forest_name")
        self.seq_identifier = load_var("seq_identifier")


    def display_base_metadata(self):
        """Affiche les metadata"""

        self.forest_name_edit.setText(str(self.seq_identifier))
        self.departement_edit.setText(str(self.dep_str))
        self.city_edit.setText(str(self.city_str))
        self.surface_edit.setText(str(self.surface_formatted))
        self.surface_boisee_edit.setText(str(self.wooded_surface))
        self.surface_non_boisee_edit.setText(str(self.no_wooded_surface))
        self.owner_edit.setText(str(self.owner_str))        

        if self.forest_name :
            self.forest_name_edit.setText(str(self.forest_name))
            prefix = self.forest_name.split(" ")[0]
            for cb, label in self.forestType_rb.items():
                cb.setChecked(label == prefix)

    # endregion
    # ================================================
    # region Forest type and name
    # ================================================

    def on_checkbox_toggled(self, checked):
        """
        Gère la sélection des checkboxes de type de propriété.

        - Si aucun projet n'est sélectionné, toutes les checkboxes sont invisibles.
        - Les checkboxes sont rendues mutuellement exclusives.
        - Met à jour le nom de la forêt en fonction de la sélection.

        """
        seq_dir = get_project_variable("QS2_seq_dir")
        seq_identifier = get_project_variable("QS2_seq_identifier")

        if not checked:
            return

        if not seq_dir or not seq_identifier :
            # Aucun projet => décocher toutes
            for rb in self.nom_checkbox:
                if rb.isChecked():
                    rb.blockSignals(True)
                    rb.setChecked(False)
                    rb.blockSignals(False)
            return
        
        seq_dir = Path(seq_dir)

        if checked:
            # Une checkbox a été cochée, décocher toutes les autres
            sender_rb = self.sender()
            for rb in self.forestType_rb:
                if rb != sender_rb and rb.isChecked():
                    rb.blockSignals(True)
                    rb.setChecked(False)
                    rb.blockSignals(False)

        prefix = next((label for rb, label in self.forestType_rb.items() if rb.isChecked()), "")
        forest_name = update_forest_name(prefix, seq_identifier)

        set_project_variable("QS2_forest_name", forest_name)

        self.forest_name_edit.setText(str(forest_name))

    # endregion