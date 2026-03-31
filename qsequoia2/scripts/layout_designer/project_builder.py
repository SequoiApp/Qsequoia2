
from qsequoia2.scripts.utils.variable import get_global_variable, get_project_variable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from ..utils.seq_config import seq_layer, seq_read
from ..utils.wmts import wmts_layer, wmts_read
from ..utils.messageBar import messageBar, messageLog

from qgis.core import QgsProject

class ProjectBuilder:

    def __init__(self, iface, seq_id, config, project_key: str):

        self.iface = iface
        self.seq_id = seq_id
        self.config = config
        self.project_key = project_key

        self.project = QgsProject.instance()

        self.canvas = self.config.get_canvas(project_key)
        self.layout = self.config.get_layout(project_key)

        self.zoom_on = self.canvas.zoom_on

    def build(self):

        messageBar(self.iface, f"Création de la mise en page : {self.project_key}", "i", 8)

        group_name = f"{self.seq_id} - {self.project_key.upper()}"
        main_group = self._get_group(group_name)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layers = self._load_layers(main_group)
            messageLog(f"Layers chargées : {list(layers.keys())}")
        finally:
            QApplication.restoreOverrideCursor()

        zoom_layer = layers.get(self.zoom_on) if self.zoom_on else None
        messageLog(f"Zoom sur : {self.zoom_on} -> {zoom_layer}")

        if zoom_layer:
            self._zoom_to_layer(zoom_layer)

        self._fold_all()

        messageBar(self.iface, f"Mise en page {self.project_key} chargée avec succès", "s", 8)

    def _get_group(self, name, parent=None):
        parent = parent or self.project.layerTreeRoot()
        group = parent.findGroup(name)
        return group if group else parent.addGroup(name)

    def _load_layers(self, main_group):

        layers_key = self.config.get_layers(self.project_key)

        project_folder = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")

        if not project_folder:
            messageBar(self.iface, "Aucun projet sélectionné", "w")
            return {}

        seq_layers = self._load_seq_layers(layers_key.sequoia, main_group, project_folder, style_folder)
        wmts_layers = self._load_wmts_layers(layers_key.wmts, main_group)

        return seq_layers | wmts_layers

    def _load_seq_layers(self, keys, main_group, project_folder, style_folder):

        seq_layers = {}
        errors = []
        for seq_key in keys:
            try:
                meta = seq_layer(seq_key)
                family = (meta.get("family") or "autres").upper()

                group = self._get_group(family, parent=main_group)

                layer = seq_read(
                    seq_key,
                    project_folder=project_folder,
                    add_to_project=True,
                    group=group,
                    style_folder=style_folder
                )

                if layer:
                    seq_layers[seq_key] = layer

            except Exception as e:
                errors.append(f"{seq_key}: {e}")
                messageLog(f"[SEQ] {seq_key} failed: {e}")
        
        return seq_layers

    def _load_wmts_layers(self, keys, main_group):

        wmts_layers = {}
        errors = []
        for wmts_key in keys:
            try:
                meta = wmts_layer(wmts_key)
                family = (meta.get("family") or "autres").upper()

                group = self._get_group(family, parent=main_group)
                layer = wmts_read(key=wmts_key, group=group)

                if layer:
                    wmts_layers[wmts_key] = layer

            except Exception as e:
                errors.append(f"{wmts_key}: {e}")
                messageLog(f"[WMTS] {wmts_key} failed: {e}")
        
        return wmts_layers

    def _zoom_to_layer(self, layer, margin=1.1):
        extent = layer.extent()
        extent.scale(margin)

        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

    def _fold_all(self):
        root = self.project.layerTreeRoot()
        for child in root.children():
            child.setExpanded(False)
        root = self.project.layerTreeRoot()
        for node in root.children():
            node.setExpanded(False)