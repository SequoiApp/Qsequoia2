from datetime import datetime
from pathlib import Path

from qgis import processing
from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
    QgsProviderRegistry,
)

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget, QTreeWidgetItem, QApplication
from PyQt5.QtCore import Qt

from qsequoia2.modules.utils.variable import get_project_variable, get_global_variable
from qsequoia2.modules.utils.seq_config import seq_read, seq_layer
from qsequoia2.modules.utils.Qmessage import messageBar, messageLog

UI_PATH = Path(__file__).parent / "tools.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

class ToolsDialog(QWidget, FORM_CLASS):

    def __init__(self, iface, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.dock = parent

        self.setupUi(self)

        self._init_tree()
        
    def _init_tree(self):

        self.tw_tools.clear()
        self.tw_tools.setHeaderLabels(["UA Tools"])

        clean_item = QTreeWidgetItem(["Nettoyer UA"])
        clean_item.setData(0, Qt.UserRole, self._run_clean_ua)

        self.tw_tools.addTopLevelItem(clean_item)

        self.tw_tools.itemDoubleClicked.connect(self._run)

    def _run(self, item):
        func = item.data(0, Qt.UserRole)
        if callable(func):
            func()

    def _run_clean_ua(self):
        seq_dir = get_project_variable("QS2_seq_dir")
        style_folder = get_global_variable("QS2_styles_directory")

        if not seq_dir:
            raise RuntimeError("Aucune forêt sélectionnée")

        QApplication.setOverrideCursor(Qt.WaitCursor)
        messageBar(self.iface, "Nettoyage UA en cours...", "i", duration=0)

        try:
            ua_layer = seq_read("v.seq.ua", seq_dir, add_to_project=True)
            if not ua_layer or not ua_layer.isValid():
                raise RuntimeError("Impossible de charger la couche UA")

            ua_name = seq_layer("v.seq.ua")["name"]
            ua_source = ua_layer.source()

            backup_path = self.backup_ua(ua_layer, ua_name, ua_source)

            # 2. run cleaning algo
            cleaned_ua = self.clean_ua(ua_layer)

            QgsProject.instance().removeMapLayer(ua_layer.id())

            # write cleaned layer directly
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = "GPKG"
            options.layerName = ua_name
            options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

            err, msg, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
                cleaned_ua,
                str(ua_source),
                QgsProject.instance().transformContext(),
                options
            )

            if err != QgsVectorFileWriter.NoError:
                raise RuntimeError(msg)

            seq_read("v.seq.ua", seq_dir, add_to_project=True, style_folder=style_folder) 
                
            messageBar(self.iface, f"UA nettoyée. Sauvegarde : {backup_path}", "s")

        except Exception as e:
            messageLog(f"[TOOLS] ERROR: {e}")
            messageBar(self.iface, f"Erreur : {str(e)}", "w")
        
        finally:
            QApplication.restoreOverrideCursor()

    def backup_ua(self, layer, name, source):

        date_str = datetime.now().strftime("%Y%m%dT%H%M%S")
        source = Path(source)
        backup_path = source.with_name(f"{source.stem}_{date_str}{source.suffix}")

        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = name
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        err, msg, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            str(backup_path),
            QgsProject.instance().transformContext(),
            options,
        )

        if err != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"Impossible d'écrire la sauvegarde : {msg}")

        return backup_path
        
    def clean_ua(self, ua_layer):

        clean = processing.run(
            "grass:v.clean",
            {
                "input": ua_layer,
                "type": [4],
                "tool": 1,
                "threshold": 0.05,
                "GRASS_SNAP_TOLERANCE_PARAMETER": 0.2,
                "output": "TEMPORARY_OUTPUT",
                "error": "TEMPORARY_OUTPUT"
            }
        )["output"]

        clean = processing.run(
            "native:deleteduplicategeometries",
            {"INPUT": clean, "OUTPUT": "TEMPORARY_OUTPUT"}
        )["OUTPUT"]

        processing.run(
            "qgis:selectbyexpression",
            {
                "INPUT": clean,
                "EXPRESSION": "$area < 20",
                "METHOD": 0
            }
        )

        clean = processing.run(
            "qgis:eliminateselectedpolygons",
            {"INPUT": clean, "MODE": 2, "OUTPUT": "TEMPORARY_OUTPUT"}
        )["OUTPUT"]


        # overwrite UA
        clean = processing.run(
            "native:fixgeometries",
            {"INPUT": clean, "OUTPUT": "TEMPORARY_OUTPUT"}
        )["OUTPUT"]

        clean = processing.run(
            "native:multiparttosingleparts",
            {"INPUT": clean, "OUTPUT": "TEMPORARY_OUTPUT"}
        )["OUTPUT"]

        return clean
    