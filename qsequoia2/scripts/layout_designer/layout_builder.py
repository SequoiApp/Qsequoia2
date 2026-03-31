

import os,json

from qsequoia2.scripts.add_on.templates.basic_addon import data
from qsequoia2.scripts.utils.variable import get_global_variable, get_project_variable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ..utils.seq_config import seq_layer, seq_read
from ..utils.wmts import wmts_layers, wmts_read
from ..utils.messageBar import messageBar, messageLog

from qgis.core import QgsProject

class LayoutBuilder:

    def __init__(self, iface, seq_id, config, project_key: str):

        self.iface = iface
        self.seq_id = seq_id
        self.config = config
        self.project_key = project_key

        self.project = QgsProject.instance()

        self.canvas = self.config.get_canvas(project_key)
        self.layout = self.config.get_layout(project_key)

        self.zoom_on = self.canvas.zoom_on

    def _build(self):

        messageBar(self.iface, f"Création de la mise en page : {self.project_key}", "i", 8)

        group_name = f"{self.seq_id} - {self.project_key.upper()}"
        main_group = self.project.layerTreeRoot().addGroup(group_name)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layers = self._load_layers(main_group)
            messageLog(f"layers : {layers}")
        finally:
            QApplication.restoreOverrideCursor()

        zoom_layer = layers.get(self.zoom_on) if self.zoom_on else None
        messageLog(f"Zoom sur la couche : {self.zoom_on} - {zoom_layer}")
        if zoom_layer:
            self._zoom_to_layer(zoom_layer)

        self._fold_all()

        messageBar(self.iface, f"Mise en page {self.project_key} chargée avec succès", "s", 8)

    def _load_layers(self, main_group):

        layers_key = self.config.get_layers(self.project_key)

        project_folder = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")
        
        errors = []
        layers = {}

        if not project_folder:
            messageBar(self.iface, "Aucun projet sélectionné", "w")
            return

        for seq_key in layers_key.sequoia:
            try:
                meta = seq_layer(seq_key)
                family = meta.get("family") or "autres"
                group_name = family.upper()

                sub_group = main_group.findGroup(group_name)
                if not sub_group:
                    sub_group = main_group.addGroup(group_name)

                layer = seq_read(
                    seq_key,
                    project_folder=project_folder,
                    add_to_project=True,
                    group = sub_group,
                    style_folder=style_folder
                )
                layers[seq_key] = layer

            except Exception:
                pass

        for wmts_key in layers_key.wmts:
            try:
                meta = wmts_layers(wmts_key)
                family = meta.get("family") or "autres"
                group_name = family.upper()

                sub_group = main_group.findGroup(group_name)
                if not sub_group:
                    sub_group = main_group.addGroup(group_name)

                wmts_read(key=wmts_key, group=sub_group)
                
            except Exception as e:
                messageBar(self.iface, f"Erreur: {e}", "c")
        
        if errors:
            message = "Couches non disponibles :\n- " + "\n- ".join(errors)
            messageBar(self.iface, message, "w", 10)

        return layers

    def _zoom_to_layer(self, layer, margin=1.1):
        extent = layer.extent()
        extent.scale(margin)

        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

    def _fold_all(self):
        root = self.project.layerTreeRoot()
        for node in root.children():
            node.setExpanded(False)