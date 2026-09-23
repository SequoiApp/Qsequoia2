from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import Qt
from qgis.PyQt.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
from qgis.core import QgsMapLayer, QgsProject

from qsequoia2.modules.utils.variable import get_global_variable, get_project_variable

from ..utils.Qmessage import  messageLog
from ..utils.seq_config import seq_read
from ..utils.wmts import wmts_read
from ..utils.tms import tms_read
from ..utils.qgz_project import open_seq_project

@dataclass
class BuildContext:
    seq_id: Optional[str]
    canvas: object
    layers: dict[str, QgsMapLayer]

class ProjectBuilder:

    def __init__(self, iface, project: QgsProject, seq_id: Optional[str], seq_dir, canvas_cfg, on_project_loaded=None):
        self.iface = iface
        self.project = project
        self.seq_id = seq_id
        self.seq_dir = seq_dir
        self.canvas_cfg = canvas_cfg
        self.on_project_loaded = on_project_loaded

    def build(self) -> BuildContext:

        suffix = self.canvas_cfg.key.upper()

        path = open_seq_project(
            self.project,
            self.iface,
            self.seq_id,
            self.seq_dir,
            suffix = suffix,
            ask_create=True,
            ask_unsaved=True,
            preserve_qs2_variables=True
        )

        if not path:
            return

        messageLog(f"[PROJECT] Opened project: {path}")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layers = {}
            layers |= self._load_seq_layers(self.canvas_cfg.layers.sequoia)
            layers |= self._load_wmts_layers(self.canvas_cfg.layers.wmts)
            layers |= self._load_tms_layers(self.canvas_cfg.layers.tms)
        finally:
            QApplication.restoreOverrideCursor()

        zoom_layer = layers.get(self.canvas_cfg.zoom_on) if self.canvas_cfg.zoom_on else None
        if zoom_layer:
            # Wait for Qt even loop to finish; otherwise canvas doesn't zoom to zoom_on layer
            QTimer.singleShot(0, lambda: self._zoom_to_layer(zoom_layer))

        self._fold_all()

        if self.on_project_loaded:
            self.on_project_loaded()
            messageLog(f"[PROJECT BUILDER] on_project_loaded emitted")

        return BuildContext(
            seq_id=self.seq_id,
            canvas=self.canvas_cfg,
            layers=layers,
        )

    def _load_seq_layers(self, keys) -> dict[str, QgsMapLayer]:
        seq_dir = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")

        if not seq_dir:
            raise RuntimeError("[Projet] Aucun projet sélectionné")

        loaded = {}

        for key in keys:
            try:
                layer = seq_read(
                    key,
                    seq_dir=seq_dir,
                    add_to_project=True,
                    style_folder=style_folder
                )
                if layer:
                    loaded[key] = layer

            except Exception as e:
                messageLog(f"[SEQ] {key} failed: {e}")

        return loaded

    def _load_wmts_layers(self, keys) -> dict[str, QgsMapLayer]:
        loaded = {}

        for key in keys:
            try:
                layer = wmts_read(key=key)
                if layer:
                    loaded[key] = layer

            except Exception as e:
                messageLog(f"[WMTS] {key} failed: {e}")

        return loaded
    
    def _load_tms_layers(self, keys) -> dict[str, QgsMapLayer]:
        loaded = {}

        for key in keys:
            try:
                layer = tms_read(key=key)
                if layer:
                    loaded[key] = layer

            except Exception as e:
                messageLog(f"[TMS] {key} failed: {e}")

        return loaded

    def _zoom_to_layer(self, layer, margin=1.1):
        extent = layer.extent()
        extent.scale(margin)

        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

    def _fold_all(self):
        self.iface.layerTreeView().collapseAll()
