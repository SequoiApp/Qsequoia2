from qgis.core import QgsFeatureRequest
from collections import defaultdict
from ..utils.seq_config import seq_field

class ForestMetadataBuilder:
    """Compute forest metadata from PARCA, with optional UA surfaces."""

    TRUE_VALUES = {True, 1, "1", "true", "vrai", "yes", "oui"}

    def __init__(self, parca, ua=None):
        self.parca = parca
        self.ua = ua

    def build(self) -> dict:
        metadata = {
            "com_name": self._aggregate_parca("com_name"),
            "owner": self._aggregate_parca("owner"),
            "dep_code": self._aggregate_parca("dep_code"),
            "dep_name": self._aggregate_parca("dep_name"),
            "reg_name": self._aggregate_parca("reg_name"),
            "surface_total": self._surface_parca(),
        }

        if self.ua and self.ua.isValid():
            metadata["surface_soumise"] = self._surface_ua("is_dgd")
            metadata["surface_boisee"] = self._surface_ua("is_wooded")

        return metadata

    def _field(self, key):
        return seq_field(key)["name"]

    def _as_float(self, value):
        return float(value or 0.0)

    def _is_true(self, value):
        if isinstance(value, str):
            value = value.strip().lower()
        return value in self.TRUE_VALUES

    def _aggregate_parca(self, field_key):
        field = self._field(field_key)
        area_field = self._field("cad_area")

        data = defaultdict(float)

        for f in self.parca.getFeatures():
            name = str(f[field] or "").strip()
            data[name] += self._as_float(f[area_field])

        return [
            {"name": name, "surface": surface}
            for name, surface in data.items()
        ]

    def _surface_parca(self):
        area_field = self._field("cad_area")

        return sum(
            self._as_float(f[area_field])
            for f in self.parca.getFeatures()
        )

    def _surface_ua(self, bool_field_key):
        area_field = self._field("cor_area")
        bool_field = self._field(bool_field_key)

        return sum(
            self._as_float(f[area_field])
            for f in self.ua.getFeatures()
            if self._is_true(f[bool_field])
        )