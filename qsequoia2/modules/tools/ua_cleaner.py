import gc
from datetime import datetime
from pathlib import Path
from shutil import copy2
from typing import Optional

from qgis import processing
from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsVectorFileWriter,
)

from qsequoia2.modules.utils.seq_config import resolve_seq_layer, seq_read


def run_clean_ua(seq_dir: str, style_folder: Optional[str] = None):
    """
    Full UA cleaning pipeline.

    Returns:
        backup_path (Path)
    """

    project = QgsProject.instance()
    ua_layer = resolve_seq_layer("v.seq.ua", project)

    is_loaded = ua_layer is not None
    if is_loaded:
        project.removeMapLayer(ua_layer.id())
        ua_layer = None

    ua_layer = seq_read("v.seq.ua", seq_dir, add_to_project=False)

    ua_source = Path(ua_layer.source())
    backup_path = backup_ua(ua_source)
    cleaned = clean_ua(ua_layer)

    write_cleaned_layer(cleaned, ua_source)

    # reload clean layer
    seq_read("v.seq.ua", seq_dir, add_to_project=True, style_folder=style_folder)

    return backup_path


def backup_ua(ua_source: Path) -> Path:
    """Copy the complete current GeoPackage before replacing it."""
    if not ua_source.is_file():
        raise FileNotFoundError(f"GeoPackage UA introuvable : {ua_source}")

    date_str = datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_path = ua_source.with_name(f"{ua_source.stem}_{date_str}{ua_source.suffix}")

    copy2(ua_source, backup_path)

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


def write_cleaned_layer(layer, path: Path):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = path.stem
    # Recreate the GeoPackage so no previous layer can remain beside the UA.
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer

    err, msg, *_ = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer,
        str(path),
        QgsProject.instance().transformContext(),
        options
    )

    if err != QgsVectorFileWriter.NoError:
        raise RuntimeError(msg)
