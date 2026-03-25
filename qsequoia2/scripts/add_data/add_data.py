import yaml
from pathlib import Path

from PyQt5 import uic
from qgis.PyQt.QtGui import QColor, QBrush
from PyQt5.QtWidgets import QTabWidget
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem
from qgis.PyQt.QtCore import Qt

from qgis.core import QgsRasterLayer, QgsProject

from ..utils.seq_config import seq_layer, get_seq_config, seq_read
from ..utils.variable import get_global_variable, get_project_variable
from ..utils.messageBar import messageBar, messageLog

UI_PATH = Path(__file__).parent / "add_data.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

VTAB_INDEX = 0
RTAB_INDEX = 1
WTAB_INDEX = 2

class AddDataTabWidget(QTabWidget, FORM_CLASS):
    """
    When Qsequoia2 is loaded, no project folder is selected, so all layers are initially unavailable.

    When a folder is selected, the `projectChanged` signal is emitted.
    This signal triggers a rebuild of the vector and raster tabs using the selected folder.

    During this rebuild, layer availability is evaluated so that only accessible layers are enabled.
    """

    def __init__(self, iface, parent=None):

        super().__init__(parent)
        self.iface = iface
        self.project = QgsProject.instance()

        self.setupUi(self)

        self.layers = [seq_layer(key) for key in get_seq_config("seq_layers").keys()]

        self.add_vecteur_tab()
        self.add_raster_tab()
        self.add_wmts_tab()

    def add_vecteur_tab(self, seq_dir=None):

        tab = QWidget()
        layout = QVBoxLayout(tab)

        tree = QTreeWidget()
        tree.setObjectName("vtree")
        tree.setHeaderLabels(["Vecteurs"])

        # Filter + sort layers
        layers_vect = [l for l in self.layers if l["type"] == "vect"]
        layers_vect = sorted(layers_vect, key=lambda l: (l["family"] or "autres").lower())

        categories = {}

        for l in layers_vect:

            # Normalize family
            raw_family = l["family"] or "autres"
            family_key = raw_family.lower()              # for grouping
            family_label = raw_family.capitalize()       # for display

            # Create category if needed
            if family_key not in categories:
                cat_item = QTreeWidgetItem([family_label])
                tree.addTopLevelItem(cat_item)
                categories[family_key] = cat_item

            # Add layer
            item = QTreeWidgetItem([l["name"]])
            item.setData(0, Qt.UserRole, l)

            # Grey if not available
            if not self.is_available(l, seq_dir):
                item.setDisabled(True)

            categories[family_key].addChild(item)

        layout.addWidget(tree)
        self.insertTab(VTAB_INDEX, tab, "VECTEUR")
        tree.itemDoubleClicked.connect(self.on_seq_layer_clicked)

        return tab

    def add_raster_tab(self, seq_dir=None):

        tab = QWidget()
        layout = QVBoxLayout(tab)

        tree = QTreeWidget()
        tree.setObjectName("rtree")
        tree.setHeaderLabels(["Raster"])

        # Filter + sort layers
        layers_rast = [l for l in self.layers if l["type"] == "rast"]
        layers_rast = sorted(layers_rast, key=lambda l: (l["family"] or "autres").lower())

        categories = {}

        for l in layers_rast:

            # Normalize family
            raw_family = l["family"] or "autres"
            family_key = raw_family.lower()              # for grouping
            family_label = raw_family.capitalize()       # for display

            # Create category if needed
            if family_key not in categories:
                cat_item = QTreeWidgetItem([family_label])
                tree.addTopLevelItem(cat_item)
                categories[family_key] = cat_item

            # Add layer
            item = QTreeWidgetItem([l["name"]])
            item.setData(0, Qt.UserRole, l)

            # Grey if not available
            if not self.is_available(l, seq_dir):
                item.setDisabled(True)

            categories[family_key].addChild(item)

        layout.addWidget(tree)
        self.insertTab(RTAB_INDEX, tab, "RASTER")
        tree.itemDoubleClicked.connect(self.on_seq_layer_clicked)

        return tab
        
    def add_wmts_tab(self):

        tab = QWidget()
        layout = QVBoxLayout(tab)

        tree = QTreeWidget()
        tree.setObjectName("wmts_tree")
        tree.setHeaderLabels(["WMTS"])

        yaml_path = Path(__file__).parents[2] / "inst" / "wmts.yaml"
        wmts_cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

        wmts_items = sorted(
            wmts_cfg.values(),
            key=lambda w: (w.get("family") or "autres").lower()
        )

        categories = {}

        for wmts in wmts_items:

            raw_family = wmts.get("family", "autres")
            family_key = raw_family.lower()
            family_label = raw_family.capitalize()

            if family_key not in categories:
                cat_item = QTreeWidgetItem([family_label])
                tree.addTopLevelItem(cat_item)
                categories[family_key] = cat_item

            item = QTreeWidgetItem([wmts["display_name"]])
            item.setData(0, Qt.UserRole, wmts)

            categories[family_key].addChild(item)

        layout.addWidget(tree)
        self.insertTab(WTAB_INDEX, tab, "WMTS")
        tree.itemDoubleClicked.connect(self.on_wmts_clicked)

        return tab
  
    @staticmethod
    def is_available(layer, folder):
        if not folder:
            return False
        # Return at first match to avoid full scan
        return any(Path(folder).rglob(f"*{layer.get('filename','')}"))
    
    # region ADD LAYER TO QGIS
    def on_seq_layer_clicked(self, item, column):

        project_folder = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")

        data = item.data(0, Qt.UserRole)

        # Ignore category clicks
        if not data:
            return

        if not project_folder:
            messageBar(self.iface, "Aucun projet sélectionné", "w")
            return

        # Safe group name
        key = data["key"]
        family = data.get("family") or "AUTRES"
        group_name = family.upper()

        try:
            seq_read(
                key=key,
                seq_dir=project_folder,
                add_to_project=True,
                group_name=group_name,
                style_folder=style_folder
            )

        except Exception as e:
            messageBar(self.iface, f"Erreur: {e}", "c")

    def on_wmts_clicked(self, item, column):

        data = item.data(0, Qt.UserRole)

        # Ignore category clicks
        if not data:
            return

        url = data.get("url")
        name = item.text(0)

        if not url:
            messageBar(self.iface, "URL WMTS invalide", "w")
            return

        group_name = "WMTS"

        try:
            # Create WMTS layer
            layer = QgsRasterLayer(url, name, "wms")
            messageLog(f"layer:{layer}")

            if not layer.isValid():
                raise RuntimeError("WMTS layer invalide")

            root = self.project.layerTreeRoot()

            # Add to group
            group = root.findGroup(group_name)
            if not group:
                group = root.addGroup(group_name)

            self.project.addMapLayer(layer, False)
            group.addLayer(layer)

        except Exception as e:
            messageBar(self.iface, f"Erreur WMTS: {e}", "c")
    # endregion

    # region UPDATE FROM SIGNAL
    def on_project_changed(self, seq_dirname, seq_dir):
        self._reload_vecteur_tab(seq_dir)
        self._reload_raster_tab(seq_dir)

    def _reload_vecteur_tab(self, seq_dir):
        # Find where is user
        current = self.currentIndex()

        self.removeTab(VTAB_INDEX)
        self.add_vecteur_tab(seq_dir)

        # Restore user position
        self.setCurrentIndex(current)

    def _reload_raster_tab(self, seq_dir):
        # Find where is user
        current = self.currentIndex()

        self.removeTab(RTAB_INDEX)
        self.add_raster_tab(seq_dir)

        # Restore user position
        self.setCurrentIndex(current)

    # endregion