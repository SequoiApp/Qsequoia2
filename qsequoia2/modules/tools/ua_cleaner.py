from datetime import datetime
from pathlib import Path

from qgis import processing
from qgis.core import (
    QgsProject,
    QgsVectorFileWriter,
)

from qsequoia2.modules.utils.seq_config import seq_read, seq_layer


def run_clean_ua(seq_dir: str, style_folder: str | None = None):
    """
    Full UA cleaning pipeline.

    Returns:
        backup_path (Path)
    """

    ua_layer = seq_read("v.seq.ua", seq_dir, add_to_project=True)
    if not ua_layer or not ua_layer.isValid():
        raise RuntimeError("Impossible de charger la couche UA")

    ua_name = seq_layer("v.seq.ua")["name"]
    ua_source = Path(ua_layer.source())

    backup_path = backup_ua(ua_layer, ua_name, ua_source)

    cleaned = clean_ua(ua_layer)

    QgsProject.instance().removeMapLayer(ua_layer.id())

    write_cleaned_layer(cleaned, ua_source, ua_name)

    # reload clean layer
    seq_read(
        "v.seq.ua",
        seq_dir,
        add_to_project=True,
        style_folder=style_folder
    )

    return backup_path

def backup_ua(layer, name, source: Path) -> Path:
    date_str = datetime.now().strftime("%Y%m%dT%H%M%S")
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

def clean_ua(ua_layer):
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

    clean = processing.run(
        "native:fixgeometries",
        {"INPUT": clean, "OUTPUT": "TEMPORARY_OUTPUT"}
    )["OUTPUT"]

    clean = processing.run(
        "native:multiparttosingleparts",
        {"INPUT": clean, "OUTPUT": "TEMPORARY_OUTPUT"}
    )["OUTPUT"]

    return clean

def write_cleaned_layer(layer, path: Path, name: str):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = name
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    err, msg, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer,
        str(path),
        QgsProject.instance().transformContext(),
        options
    )

    if err != QgsVectorFileWriter.NoError:
        raise RuntimeError(msg)