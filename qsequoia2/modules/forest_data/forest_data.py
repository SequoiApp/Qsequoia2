
# ==========================================================================
# import
# ==========================================================================

# python 

from pathlib import Path
import json

# Qgis
from PyQt5 import uic
from qgis.PyQt.QtWidgets import QWidget
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

PROJECT = QgsProject.instance()

# ==========================================================================
# region initalisation
# ==========================================================================

class ForestDataTabs(QWidget, FORM_CLASS):
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
            rb.setEnabled(False)
            self.lbl_type.setEnabled(False)
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
            rb.setEnabled(True)
            self.lbl_type.setEnabled(True)

        # création des métadata 
        seq_metadata = self.run_calculation(seq_dir)
        self.export_to_project_variables(seq_metadata, seq_dir)
        PROJECT.write() # sauvegarde du projet pour que les variables soient prises en compte dans les expressions QGIS

        # lecture des metadata
        self.display_base_metadata(seq_metadata)


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
            print("Export metadata : ", f"QS2_{key} : {value}")
            set_project_variable(f"QS2_{key}", str(value))

        messageLog(f"-- metadata build pour {seq_dir} --!","i")


    # ================================================
    # Metadata Lecture et affichage
    # ================================================

    # TODO : Revoir ca ne fonctionne pas les varaibles sont néanmoins dispo via @..  

    def _extract_group(self, seq_metadata, prefix):
        items = []

        i = 1
        while True:
            name_key = f"QS2_{prefix}_{i}_name"
            surf_key = f"QS2_{prefix}_{i}_surface"

            if name_key not in seq_metadata:
                break

            items.append({
                "name": seq_metadata.get(name_key, ""),
                "surface": seq_metadata.get(surf_key, 0)
            })

            i += 1

        return items
    
    def display_base_metadata(self, m):


        for prefix, widget in {
            "city": self.city_le,
            "owner": self.owner_le,
            "dep_name": self.dep_code_le,
            "reg_name": self.reg_name_le,
        }.items():

            group = self._extract_group(m, prefix)
            widget.setText(", ".join(g["name"] for g in group))

        for key, widget in {
            "total_surface": self.total_surface_le,
            "wooded_surface": self.wooded_surface_le,
            "no_wooded_surface": self.no_wooded_surface_le,
        }.items():

            widget.setText(str(m.get(key, "")))

        # if self.forest_name :
        #     self.seq_id_edit.setText(str(self.forest_name))
        #     prefix = self.forest_name.split(" ")[0]
        #     for cb, label in self.forestType_rb.items():
        #         cb.setChecked(label == prefix)

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
        seq_id = get_project_variable("QS2_seq_id")

        if not checked:
            return

        if not seq_dir or not seq_id :
            # Aucun projet => décocher toutes
            for rb in self.forestType_rb:
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
        forest_name = update_forest_name(prefix, seq_id)

        set_project_variable("QS2_forest_name", forest_name)

        self.seq_id_edit.setText(str(forest_name))

    # endregion