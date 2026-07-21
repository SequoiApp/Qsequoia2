from pathlib import Path

import processing

from qsequoia2.modules.utils.Qmessage import messageBox, messageBar
from qsequoia2.modules.utils.seq_config import find_seq_id, seq_layer


class PltMerger:
    def __init__(self, iface, seq_dir, key: str = "plt"):
        self.iface = iface
        self.seq_dir = Path(seq_dir)
        self.meta = seq_layer(key)

    @property
    def root(self) -> Path:
        return self.seq_dir / self.meta["path"]

    @property
    def output(self) -> Path:
        seq_id = find_seq_id(self.seq_dir)
        return self.root / f"{seq_id}_{self.meta['filename']}"

    def find_rasters(self) -> list[Path]:
        if not self.root.is_dir():
            return []

        pattern = f"*_{self.meta['name']}*.{self.meta['ext']}"

        return sorted(
            path
            for path in self.root.glob(pattern)
            if path != self.output
        )

    def open_dialog(self) -> None:
        rasters = self.find_rasters()

        if not rasters:
            messageBox(
                self.iface,
                "Fusion des rasters",
                "Aucun raster contenant « _PLT » n’a été trouvé.",
                "i",
            )
            return

        result = processing.execAlgorithmDialog(
            "gdal:merge",
            {
                "INPUT": [str(path) for path in rasters],
                "PCT": False,
                "SEPARATE": False,
                "NODATA_INPUT": 0,
                "NODATA_OUTPUT": 0,
                "DATA_TYPE": 0,
                "CREATION_OPTIONS": "COMPRESS=DEFLATE|TILED=YES",
                "EXTRA": "",
                "OUTPUT": str(self.output),
            },
        )

        if result and self.output.exists():
            messageBar(
                self.iface,
                f"Rasters fusionnés : {self.output}",
                "s",
            )