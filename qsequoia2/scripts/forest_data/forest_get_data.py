
from collections import defaultdict
from ..utils.config import *
from ..utils.messageBar import *
from ..utils.seq_config import *
from ..utils.yaml_helper import *
from ..utils.variable import *

# Mise en forme 

DEFAULT_FORMATTING = {"separator": ", ", "last_separator": " & "}
DEFAULT_SURFACE = {
    "text_total": "Surface totale",
    "text_boisee": "Surface boisée"
}

#===================================================
# region getForestdata
#===================================================

class getForestdata:
    """
    Centralise la lecture, le traitement et l'agrégation des données forestières
    depuis les couches SIG PARCA et UA dans QGIS.

    Méthodes principales :
    - build() : construit toutes les métadonnées forestières et retourne un dict.
    - set_city_data() : calcule les surfaces par commune.
    - set_owner_data() : calcule les surfaces par propriétaire.
    - forest_departements() : récupère et agrège les départements des parcelles.
    - _set_surface() : calcule surfaces boisées, non boisées et totale.
    """

    def __init__(self, iface, seq_dir):

        self.iface = iface
        self.seq_dir = seq_dir

    # ================================================================================================
    # appel des fonctions
    # ================================================================================================

    def build(self, ua_layer, parca_layer) -> dict :
        """Construit toutes les metadata et retourne un dict"""
        
        city_list, city_str = self.set_city_data(parca_layer)
        owner_list, owner_str = self.set_owner_data(parca_layer)
        dep_str, dep_list = self.forest_departements(parca_layer)
        wooded_surface, no_wooded_surface, total_surface, surface_formatted = self._set_surface(ua_layer, parca_layer)

        seq_metadata = {
                            "city_list": city_list,
                            "city_str": city_str,
                            "owner_list": owner_list,
                            "owner_str": owner_str,
                            "departement_str": dep_str,
                            "departement_list": dep_list,
                            "wooded_surface": wooded_surface,
                            "no_wooded_surface": no_wooded_surface,
                            "total_surface": total_surface,
                            "surface_formatted": surface_formatted
                        }
        return seq_metadata
        
    
    # ================================================================================================
    # Calcul des métadonnées
    # ================================================================================================

    def set_city_data(self, parca_layer):
        """résout les villes"""
        city_field = seq_field("com_name")["name"]
        surface_field = seq_field("cad_area")["name"]

        city_dict = defaultdict(float)
        for feat in parca_layer.getFeatures():
            commune = feat[city_field]
            surface = float(feat[surface_field] or 0.0)
            city_dict[commune] += surface

        city_list = [{"commune": k, "surface_ha": v} for k, v in city_dict.items()]
        city_values = [f"{c['commune']} ({c['surface_ha']:.4f} ha)" for c in city_list]
        city_str = self.formatting_data_str(city_values)

        return city_list, city_str


    
    def set_owner_data(self, parca_layer):
        """résout le nom des propriétaire"""
        owner_field = seq_field("owner")["name"]
        city_field = seq_field("com_name")["name"]
        surface_field = seq_field("cad_area")["name"]

        owner_dict = defaultdict(lambda: {"commune": "", "surface_ha": 0.0})
        for feat in parca_layer.getFeatures():
            commune = feat[city_field]
            owner = feat[owner_field]
            surface = float(feat[surface_field] or 0.0)
            if owner:
                owner_dict[(commune, owner)]["commune"] = commune
                owner_dict[(commune, owner)]["surface_ha"] += surface

        owner_list = [{"commune": k[0], "owner": k[1], "surface_ha": v["surface_ha"]} for k, v in owner_dict.items()]
        owner_values = list(dict.fromkeys(o["owner"] for o in owner_list))
        owner_str = self.formatting_data_str(owner_values)

        return owner_list, owner_str

    # --------------------------------------------------------
    # Récupération du ou des départements de la forêt
    # --------------------------------------------------------

    def forest_departements(self, parca_layer):
        """Récupère et agrège les départements de la propriété"""
        try:
            surface_field = seq_field("cad_area")["name"]
            dep_field = seq_field("dep_code")["name"]

            # Départements formatés en chaîne
            dep_str = self._aggregate_values(parca_layer, value_field=dep_field, surface_field=surface_field)
  
            # version liste simple
            dep_list = [d.strip() for d in dep_str.replace("&", ",").split(",")]

            return dep_str, dep_list

        except Exception as e:
            raise TypeError(f"Erreur dans forest_departements : {e}")


    def _aggregate_values(self, parca_layer, value_field, surface_field, filter_field=None, result_key=None):
        """
        Agrège les surfaces par valeur d’un champ, éventuellement groupé par filtre.

        Args:
            parca_layer (QgsVectorLayer): couche contenant les parcelles
            value_field (str): nom du champ à agréger (ex: propriétaire, département)
            surface_field (str): nom du champ contenant la surface
            filter_field (str, optional): champ utilisé pour filtrer/groupes. Defaults to None.
            result_key (str, optional): clé pour stocker le résultat dans _calculated_values. Defaults to None.

        Returns:
            str: chaîne formatée des valeurs agrégées, ex: "Propriétaire1 & Propriétaire2 (Dept1); Propriétaire3 (Dept2)"
        """

        field_names = parca_layer.fields().names()
        if value_field not in field_names or surface_field not in field_names:
            raise ValueError(f"Champ introuvable : {value_field} ou {surface_field}")

        if filter_field and filter_field not in field_names:
            filter_field = None

        groups = defaultdict(list)
        for feat in parca_layer.getFeatures():
            group = feat[filter_field] if filter_field else "No Filter"
            value = feat[value_field]
            surface = float(feat[surface_field] or 0.0)
            if value is not None:
                groups[group].append((value, surface))

        result_strings = []
        for group, values in groups.items():
            agg = defaultdict(float)
            for val, surf in values:
                agg[val] += surf

            # Tri par surface décroissante
            sorted_vals = sorted(agg.items(), key=lambda x: x[1], reverse=True)
            value_list = [v[0] for v in sorted_vals]

            result_string = self.formatting_data_str(value_list)
            if group != "No Filter":
                result_strings.append(f"{result_string} ({group})")
            else:
                result_strings.append(result_string)

        final_result = "; ".join(result_strings)

        return final_result
    

    def _set_surface(self, ua_layer, parca_layer):
        """Calcule les surfaces boisée, non boisée et totale via expressions QGIS."""

        layer, surface_field = self._select_surface_layer(ua_layer, parca_layer)
        if layer is None:
            messageBar(self.iface, "Attention : aucune surface exploitable trouvée", "w", 10)
            return

        occup_field = seq_field("is_wooded")["name"]

        # Expressions de filtre QGIS
        wooded_filter = f"""
            lower(trim(coalesce("{occup_field}", ''))) IN ('true','1','vrai','boisee')
        """

        no_wooded_filter = f"""
            lower(trim(coalesce("{occup_field}", ''))) NOT IN ('true','1','vrai','boisee')
        """

        wooded_surface = sum(
            float(f[surface_field] or 0.0) for f in layer.getFeatures(QgsFeatureRequest().setFilterExpression(wooded_filter)))

        no_wooded_surface = sum(
            float(f[surface_field] or 0.0) for f in layer.getFeatures(QgsFeatureRequest().setFilterExpression(no_wooded_filter)))

        total_surface = wooded_surface + no_wooded_surface 
        formatted_surface = self.get_formated_surface(wooded_surface, no_wooded_surface )

        return wooded_surface, no_wooded_surface , total_surface, formatted_surface


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

        return None, None


    # ---------------------------------------------------------
    # Formatage surface
    # ---------------------------------------------------------
    def get_formated_surface(self, wooded_surface, no_wooded_surface):
        """
        Formate les surfaces calculées selon les règles métier.

        Deux formats possibles :
        - Total + surface boisée si surface non boisée > 0
        - Conversion détaillée en ha / ares / centiares sinon

        Retourne une chaîne prête pour affichage.
        """

        decimals = int(4)

        total_surface = wooded_surface + no_wooded_surface

        if no_wooded_surface > 0:

            formatted_surface = (
                f"{DEFAULT_SURFACE['text_total']} {total_surface:.{decimals}f} ha | "
                f"{DEFAULT_SURFACE['text_boisee']} {wooded_surface:.{decimals}f} ha")

        else:

            hectares = int(total_surface)
            ares = int((total_surface - hectares) * 100)
            centiares = int(round((((total_surface - hectares) * 100) - ares) * 100))

            formatted_surface = (
                f"{DEFAULT_SURFACE['text_total']} "
                f"{hectares} ha "
                f"{ares:02} a "
                f"{centiares:02} ca"
            )

        return formatted_surface
    

    def formatting_data_str(self,values):
        """Mise en forme des données"""

        if len(values) == 1:
            return values[0]
        if len(values) == 2:
            return f"{values[0]}{DEFAULT_FORMATTING['last_separator']}{values[1]}"

        return (f"{DEFAULT_FORMATTING['separator'].join(values[:-1])}"
                f"{DEFAULT_FORMATTING['last_separator']}{values[-1]}"
                )

    