from qgis.core import QgsFeatureRequest
from collections import defaultdict
from ..utils.Qmessage import messageBar
from ..utils.seq_config import seq_field


#===================================================
# getForestdata
#===================================================

class getForestdata:
    """
    Centralise la lecture, le traitement et l'agrégation des données forestières
    depuis les couches SIG PARCA et UA dans QGIS.
    """
    def __init__(self, iface, seq_dir):

        self.iface = iface
        self.seq_dir = seq_dir

    def build(self, ua_layer, parca_layer) -> dict :
        """Construit toutes les metadata et retourne un dict"""
        metadata = {}
        city_list = self.aggregate_parca_by_field(parca_layer, "com_name")
        self._inject_series(metadata, "city", city_list)

        owner_list = self.aggregate_parca_by_field(parca_layer, "owner")
        self._inject_series(metadata, "owner", owner_list)

        num_dep_list = self.aggregate_parca_by_field(parca_layer, "dep_code")
        self._inject_series(metadata, "dep_code", num_dep_list)

        dep_list = self.aggregate_parca_by_field(parca_layer, "dep_name")
        self._inject_series(metadata, "dep_name", dep_list)

        reg_name_list = self.aggregate_parca_by_field(parca_layer, "reg_name")
        self._inject_series(metadata, "reg_name", reg_name_list)

        wooded, no_wooded, total = self._set_surface(ua_layer, parca_layer)
        metadata.update({"wooded_surface": wooded,"no_wooded_surface": no_wooded,"total_surface": total})

        return metadata
    
    def _inject_series(self, metadata, prefix, data_list):
        for i, item in enumerate(data_list, start=1):
            metadata[f"{prefix}_{i}_name"] = item["name"]
            metadata[f"{prefix}_{i}_surface"] = item["surface"]

    def aggregate_parca_by_field(self, parca_layer, field_key_name) -> list:
        """Lit les données d'un champ et les agrège par surface"""

        data_dict = defaultdict(float)
        for feat in parca_layer.getFeatures():

            field = feat[seq_field(field_key_name)["name"]].strip()
            surface = float(feat[seq_field("cad_area")["name"]] or 0.0)
            data_dict[field] += surface

        data_list = [{"name": k, "surface": v} for k, v in data_dict.items()]

        return data_list


    def _set_surface(self, ua_layer, parca_layer):
        """Calcule les surfaces boisée, non boisée et totale via expressions QGIS."""

        layer, surface_field = self._select_surface_layer(ua_layer, parca_layer)
        if layer is None:
            messageBar(self.iface, "Attention : aucune surface exploitable trouvée", "w", 10)
            return

        occup_field = seq_field("is_wooded")["name"]

        # Expressions de filtre QGIS
        wooded_filter = f"""
            lower(trim(coalesce("{occup_field}", ''))) IN ('true','1','vrai')
        """

        no_wooded_filter = f"""
            lower(trim(coalesce("{occup_field}", ''))) NOT IN ('true','1','vrai')
        """

        wooded = sum(
            float(f[surface_field] or 0.0) for f in layer.getFeatures(QgsFeatureRequest().setFilterExpression(wooded_filter))
            )

        no_wooded = sum(
            float(f[surface_field] or 0.0) for f in layer.getFeatures(QgsFeatureRequest().setFilterExpression(no_wooded_filter))
            )

        total = wooded + no_wooded

        return wooded, no_wooded, total


    def _select_surface_layer(self, ua_layer, parca_layer):
        ua_field = seq_field("cor_area")["name"]
        if ua_layer and ua_layer.isValid() and ua_field in ua_layer.fields().names():
            surfaces = [float(f[ua_field] or 0.0) for f in ua_layer.getFeatures()]
            if sum(surfaces) > 0 :
                return ua_layer, ua_field

        if parca_layer and parca_layer.isValid():
            cad_field = seq_field("cad_area")["name"]
            if cad_field in parca_layer.fields().names():
                total = sum(float(f[cad_field] or 0.0) for f in parca_layer.getFeatures())
                if total > 0:
                    return parca_layer, cad_field

        return None


    