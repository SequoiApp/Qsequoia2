from dataclasses import dataclass

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from qgis.core import QgsMapLayer, QgsProject

from qsequoia2.modules.utils.variable import get_global_variable, get_project_variable

from ..utils.Qmessage import messageBar, messageLog
from ..utils.seq_config import seq_layer, seq_read
#from ..utils.wmts import wmts_layer, wmts_read
#from ..utils.tms import tms_layer, tms_read

@dataclass
class BuildContext:
    seq_id: str | None
    canvas: object
    layers: dict[str, QgsMapLayer]

class ProjectBuilder:
    def __init__(self, iface, project: QgsProject, seq_id: str | None, canvas):
        self.iface = iface
        self.project = project
        self.seq_id = seq_id
        self.canvas = canvas

    def build(self) -> BuildContext:
        messageBar(self.iface, f"Chargement du projet {self.canvas.alias}", "i", 8)

        group_name = (
            f"{self.seq_id} - {self.canvas.key.upper()}"
            if self.seq_id else self.canvas.key.upper()
        )
        main_group = self._get_group(group_name)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            layers = {}
            layers |= self._load_seq_layers(self.canvas.layers.sequoia, main_group)
            layers |= self._load_wmts_layers(self.canvas.layers.wmts, main_group)
            layers |= self._load_tms_layers(self.canvas.layers.tms, main_group)
        finally:
            QApplication.restoreOverrideCursor()

        zoom_layer = layers.get(self.canvas.zoom_on) if self.canvas.zoom_on else None
        if zoom_layer:
            self._zoom_to_layer(zoom_layer)

        self._fold_all()

        messageBar(self.iface, f"Projet chargé : {self.canvas.alias}", "s", 8)

        return BuildContext(
            seq_id=self.seq_id,
            canvas=self.canvas,
            layers=layers,
        )

    def _get_group(self, name, parent=None):
        parent = parent or self.project.layerTreeRoot()
        group = parent.findGroup(name)
        return group if group else parent.addGroup(name)

    def _load_seq_layers(self, keys, main_group) -> dict[str, QgsMapLayer]:
        seq_dir = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")

        if not seq_dir:
            raise RuntimeError("[Projet] Aucun projet sélectionné")

        loaded = {}

        for key in keys:
            try:
                meta = seq_layer(key)
                family = (meta.get("family") or "autres").upper()
                group = self._get_group(family, parent=main_group)

                layer = seq_read(
                    key,
                    seq_dir=seq_dir,
                    add_to_project=True,
                    group_name=group,
                    style_folder=style_folder,
                )

                if layer:
                    loaded[key] = layer

            except Exception as e:
                messageLog(f"[SEQ] {key} failed: {e}")

        return loaded

    def _load_wmts_layers(self, keys, main_group) -> dict[str, QgsMapLayer]:
        loaded = {}

        for key in keys:
            try:
                meta = wmts_layer(key)
                messageLog(f"[WMTS] {meta}")
                family = (meta.get("family") or "autres").upper()
                group = self._get_group(family, parent=main_group)

                layer = wmts_read(key=key, group=group)

                if layer:
                    loaded[key] = layer

            except Exception as e:
                messageLog(f"[WMTS] {key} failed: {e}")

        return loaded
    
    def _load_tms_layers(self, keys, main_group) -> dict[str, QgsMapLayer]:
        loaded = {}

        for key in keys:
            try:
                meta = tms_layer(key)
                messageLog(f"[TMS] {meta}")
                family = (meta.get("family") or "autres").upper()
                group = self._get_group(family, parent=main_group)

                layer = tms_read(key=key, group=group)

                if layer:
                    loaded[key] = layer

            except Exception as e:
                messageLog(f"[WMTS] {key} failed: {e}")

        return loaded

    def _zoom_to_layer(self, layer, margin=1.1):
        extent = layer.extent()
        extent.scale(margin)

        canvas = self.iface.mapCanvas()
        canvas.setExtent(extent)
        canvas.refresh()

    def _fold_all(self):
        self.iface.layerTreeView().collapseAll()
