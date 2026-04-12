from qgis.core import QgsFeatureRequest
from collections import defaultdict
from ..utils.seq_config import seq_field

class ForestMetadataBuilder:
    """Compute forest metadata from PARCA and UA layers."""

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
        }

        wooded, unwooded, total = self._compute_surfaces()

        metadata.update({
            "surface_total": total,
            "surface_wooded": wooded,
            "surface_unwooded": unwooded,
        })

        return metadata

    def _aggregate_parca(self, field_key):
        field_name = seq_field(field_key)["name"]
        area_field = seq_field("cad_area")["name"]

        data = defaultdict(float)
        for f in self.parca.getFeatures():
            key = (f[field_name] or "").strip()
            data[key] += float(f[area_field] or 0.0)

        return [{"name": k, "surface": v} for k, v in data.items()]

    def _compute_surfaces(self):
        layer, field = self._select_surface_layer()

        if layer is None:
            return 0.0, 0.0, 0.0  # ✅ safe

        occup_field = seq_field("is_wooded")["name"]

        wooded_expr = f"""lower(trim(coalesce("{occup_field}", ''))) IN ('true','1','vrai')"""
        unwooded_expr = f"""lower(trim(coalesce("{occup_field}", ''))) NOT IN ('true','1','vrai')"""

        wooded = sum(
            float(f[field] or 0.0)
            for f in layer.getFeatures(QgsFeatureRequest().setFilterExpression(wooded_expr))
        )

        unwooded = sum(
            float(f[field] or 0.0)
            for f in layer.getFeatures(QgsFeatureRequest().setFilterExpression(unwooded_expr))
        )

        return wooded, unwooded, wooded + unwooded

    def _select_surface_layer(self):
        ua_field = seq_field("cor_area")["name"]

        if self.ua and self.ua.isValid() and ua_field in self.ua.fields().names():
            total = sum(float(f[ua_field] or 0.0) for f in self.ua.getFeatures())
            if total > 0:
                return self.ua, ua_field

        cad_field = seq_field("cad_area")["name"]

        if self.parca and self.parca.isValid() and cad_field in self.parca.fields().names():
            total = sum(float(f[cad_field] or 0.0) for f in self.parca.getFeatures())
            if total > 0:
                return self.parca, cad_field

        return None, None