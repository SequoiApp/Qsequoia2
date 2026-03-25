"""
Classe getForestdata

Cette classe centralise la lecture, le traitement et l'agrégation
des données forestières à partir des couches SIG (PARCA et UA)
dans QGIS. 
"""


#====================================================
# Import
#====================================================

from collections import defaultdict
from ..utils.config import *
from ..utils.messageBar import *
from ..utils.seq_config import *
from ..utils.yaml_helper import *


#===================================================
# region getForestdata
#===================================================

class getForestdata:
    """Lecture depuis une couche PARCA des donénes sur la forêt. 
        Paramètre lu depuis la table forest_data.json"""

    def __init__(self, seq_identifier, seq_dir, iface):
        """Initialise l’objet getForestdata.
            Charge la configuration JSON et YAML, résout les définitions de champs,
            récupère les couches du projet et prépare la structure interne
            pour stocker les valeurs calculées destinées à l’export JSON.
        """
        self.iface = iface
        self.seq_identifier = seq_identifier
        self.seq_dir = seq_dir
        self.script_dir = Path(__file__).parent

        # Charge YAML

        self.config = yaml_loader("forest_data.yaml","",Path(self.script_dir))

        self._calculated_values = {}

    # ================================================================================================
    # appel des fonctions et mise en forme
    # ================================================================================================


    def build(self):
        """Construit toutes les metadata et retourne un dict"""
        parca_layer = seq_read("parca", self.seq_dir)
        ua_layer = seq_read("ua", self.seq_dir)
        
        if not ua_layer:
            messageBar(self.iface, "layer 'UA not found in project","w",10)
            return
        
        if not parca_layer:
            messageBar(self.iface, "layer 'PARCA' not found in project","c",10)
            return

        self.set_city_data(parca_layer)
        self.set_owner_data(parca_layer)
        self.forest_departements(parca_layer)
        self._set_surface(ua_layer, parca_layer)

        # regroupement global
        layer_for_group = ua_layer if ua_layer else parca_layer
        self._calculated_values["grouped_values"] = self.get_grouped_values(layer_for_group)

        return self.export_to_dict()
        
    def export_to_dict(self):
        """met en forme les données dans le dict"""
        result = {
            "city": {
                "list": self._calculated_values.get("city_list", []),
                "str": self._calculated_values.get("city_str", "")
            },
            "owner": {
                "list": self._calculated_values.get("owner_list", []),
                "str": self._calculated_values.get("owner_str", "")
            },
            "departments": {
                "list": self._calculated_values.get("departement_list", []),
                "str": self._calculated_values.get("departement_str", "")
            },
            "surfaces": {
                "boisee_ha": self._calculated_values.get("surface_boisee_ha", 0.0),
                "non_boisee_ha": self._calculated_values.get("surface_non_boisee_ha", 0.0),
                "totale_ha": self._calculated_values.get("surface_totale_ha", 0.0),
                "formatted": self._calculated_values.get("surface_formatted", "")
            },
            "grouped_values": self._calculated_values.get("grouped_values", "")
            }
        return result
    
    
    # ================================================================================================
    # Calcul des métadonnées
    # ================================================================================================

    # --------------------------------------------------------
    # Définition de la ville et du propriétaire
    # --------------------------------------------------------

    def set_city_data(self, parca_layer):
        """Extrait et calcule les villes + surfaces"""
        city_field = seq_field("com_name")["name"]
        surface_field = seq_field("cad_area")["name"]

        city_dict = defaultdict(float)
        for feat in parca_layer.getFeatures():
            commune = feat[city_field]
            surface = float(feat[surface_field] or 0.0)
            city_dict[commune] += surface

        city_list = [{"commune": k, "surface_ha": v} for k, v in city_dict.items()]
        cfg_format = self.config["formatting"]
        city_values = [f"{c['commune']} ({c['surface_ha']:.4f} ha)" for c in city_list]
        city_str = (f"{cfg_format['separator'].join(city_values[:-1])}{cfg_format['last_separator']}{city_values[-1]}"
                    if len(city_values) > 1 else city_values[0])

        self._calculated_values["city_list"] = city_list
        self._calculated_values["city_str"] = city_str

    
    def set_owner_data(self, parca_layer):
        """Extrait et calcule les propriétaires + surfaces"""
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
        cfg_format = self.config["formatting"]
        owner_values = list(dict.fromkeys(o["owner"] for o in owner_list))
        owner_str = (f"{cfg_format['separator'].join(owner_values[:-1])}{cfg_format['last_separator']}{owner_values[-1]}"
                    if len(owner_values) > 1 else owner_values[0])

        self._calculated_values["owner_list"] = owner_list
        self._calculated_values["owner_str"] = owner_str

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
            self._calculated_values["departement_str"] = dep_str

            # version liste simple
            dep_list = [d.strip() for d in dep_str.replace("&", ",").split(",")]
            self._calculated_values["departement_list"] = dep_list

            return dep_list

        except Exception as e:
            raise TypeError(f"Erreur dans forest_departements : {e}")


    def _aggregate_values(self, layer_or_path, value_field, surface_field, filter_field=None, result_key=None):
        """
        Agrège les surfaces par valeur d’un champ, éventuellement groupé par filtre.

        Retourne une chaîne formatée et stocke le résultat dans _calculated_values.
        """
        from collections import defaultdict

        layer = self._resolve_layer(layer_or_path)
        field_names = layer.fields().names()

        if value_field not in field_names or surface_field not in field_names:
            raise ValueError(f"Champ introuvable : {value_field} ou {surface_field}")

        if filter_field and filter_field not in field_names:
            filter_field = None

        groups = defaultdict(list)

        for feat in layer.getFeatures():
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

            sorted_vals = sorted(agg.items(), key=lambda x: x[1], reverse=True)
            value_list = [v[0] for v in sorted_vals]

            if len(value_list) == 2:
                result_string = f"{value_list[0]} & {value_list[1]}"
            elif len(value_list) > 2:
                result_string = f"{', '.join(value_list[:-1])} & {value_list[-1]}"
            else:
                result_string = value_list[0]

            if group != "No Filter":
                result_strings.append(f"{result_string} ({group})")
            else:
                result_strings.append(result_string)

        final_result = "; ".join(result_strings)

        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}
        self._calculated_values[result_key or "grouped_values"] = final_result

        return final_result


    def _set_surface(self, ua_layer, parca_layer):
        """Calcule les surfaces boisée, non boisée et totale."""
        
        layer, surface_field = self._select_surface_layer(ua_layer, parca_layer)
        if layer is None:
            messageBar(self.iface, "Attention : aucune surface exploitable trouvée", "w", 10)
            return

        occup_field = self._get_wooded_field(layer)
        commune_field = seq_field("com_name")["name"]

        surface_boisee = 0.0
        surface_non_boisee = 0.0

        for feat in layer.getFeatures():
            surface = float(feat[surface_field] or 0.0)
            if layer == ua_layer and occup_field:
                is_wooded = self._is_feature_wooded(feat[occup_field])
                if is_wooded:
                    surface_boisee += surface
                else:
                    surface_non_boisee += surface
            else:
                surface_boisee += surface

        surface_totale = surface_boisee + surface_non_boisee

        self._calculated_values.update({
            "surface_boisee_ha": surface_boisee,
            "surface_non_boisee_ha": surface_non_boisee,
            "surface_totale_ha": surface_totale,
            "surface_formatted": self.get_formated_surface(surface_boisee, surface_non_boisee)
        })

    def _is_feature_wooded(self, value):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "vrai", "boisee"}

    def _select_surface_layer(self, ua_layer, parca_layer):
        ua_field = seq_field("cor_area")["name"]
        if ua_layer and ua_layer.isValid() and ua_field in ua_layer.fields().names():
            surfaces = [float(f[ua_field] or 0.0) for f in ua_layer.getFeatures()]
            if sum(surfaces) > 0 and len(set(surfaces)) > 1:
                return ua_layer, ua_field

        if parca_layer and parca_layer.isValid():
            cad_field = seq_field("cad_area")["name"]
            if cad_field in parca_layer.fields().names():
                total = sum(float(f[cad_field] or 0.0) for f in parca_layer.getFeatures())
                if total > 0:
                    return parca_layer, cad_field

        return None, None

    def _get_wooded_field(self, layer):
        try:
            return seq_field("is_wooded")["name"]
        except ValueError:
            messageBar(self.iface, "Champ boisé absent : toutes surfaces considérées comme boisées.", "w", 10)
            return None

    # ---------------------------------------------------------
    # Formatage surface
    # ---------------------------------------------------------
    def get_formated_surface(self, surface_boisee, surface_non_boisee):
        """
        Formate les surfaces calculées selon les règles métier.

        Deux formats possibles :
        - Total + surface boisée si surface non boisée > 0
        - Conversion détaillée en ha / ares / centiares sinon

        Retourne une chaîne prête pour affichage.
        """

        cfg = self.config["surface"]
        decimals = cfg["round_decimals"]

        surface_totale = surface_boisee + surface_non_boisee

        # -------------------------------
        # CAS 1 : surface non boisée > 0
        # -------------------------------
        if surface_non_boisee > 0:

            formatted_surface = (
                f"{cfg['text_total']} {surface_totale:.{decimals}f} {cfg['ha_label']} | "
                f"{cfg['text_boisee']} {surface_boisee:.{decimals}f} {cfg['ha_label']}"
            )

        # -------------------------------
        # CAS 2 : uniquement surface boisée
        # -------------------------------
        else:

            hectares = int(surface_totale)
            ares = int((surface_totale - hectares) * 100)
            centiares = int(round((((surface_totale - hectares) * 100) - ares) * 100))

            formatted_surface = (
                f"{cfg['text_total']} "
                f"{hectares} {cfg['ha_label']} "
                f"{ares:02} {cfg['a_label']} "
                f"{centiares:02} {cfg['ca_label']}"
            )

        return formatted_surface
    
