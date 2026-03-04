""""""

# region import
#====================================================
# Import
#====================================================

import os, yaml, glob, json
from collections import defaultdict
from qgis.core import QgsVectorLayer, QgsProject
from ..utils.config import *
from datetime import datetime

# endregion

#===================================================
# region getForestdata
#===================================================


class getForestdata:
    """Lecture depuis une couche PARCA des donénes sur la forêt. 
        Paramètre lu depuis la table forest_setting_data.json"""

    def __init__(self, project_name, project_folder, style_folder, iface):
        self.iface = iface
        self.project_name = project_name
        self.project_folder = project_folder
        self.style_folder = style_folder

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(self.script_dir, "forest_setting_data.json")
        self.yaml_file = os.path.join(self.script_dir,"..","..","inst","seq_fields.yaml")

        # Charge YAML + JSON
        self.field_definitions = self.load_field_definitions(self.yaml_file)
        self.config = self._load_config()

        self.layer = self._find_layer()
        self._calculated_values = {}

    @staticmethod
    def load_field_definitions(yaml_file):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        field_definitions = {}
        for key, val in data.items():
            names = [val["name"]] + val.get("alias", [])
            field_definitions[key] = names
        return field_definitions

    def _load_config(self):
        if not os.path.exists(self.json_path):
            raise FileNotFoundError("Fichier setting_data.json introuvable")
        with open(self.json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _resolve_field_name(self, layer, field_key, json_fallback_key=None):
        field_names = [f.name() for f in layer.fields()]
        possible_names = self.field_definitions.get(field_key, [])

        for name in possible_names:
            if name in field_names:
                return name

        # fallback vers JSON
        if json_fallback_key:
            fallback_name = self.config["fields"].get(json_fallback_key)
            if fallback_name in field_names:
                return fallback_name
            else:
                print(f" Champ '{json_fallback_key}' fallback JSON introuvable dans la couche.")
                return fallback_name
        raise ValueError(f"Aucun champ trouvé pour '{field_key}' dans la couche. Cherché: {possible_names}")

    # ---------------------------------------------------------
    # Recherche couche selon type
    # ---------------------------------------------------------
    def _find_layer(self, layer_type="PARCA"):
        """
        Recherche la première couche existante pour le type demandé
        ("PARCA" ou "UA") selon le JSON config.
        Retourne un QgsVectorLayer valide ou None.
        """
        from qgis.core import QgsVectorLayer

        labels = self.config["layers"].get(layer_type.upper(), [])

        for label in labels:
            layer_dict = get_path(
                label=label,
                project_name=self.project_name,
                project_folder=self.project_folder,
                style_folder=self.style_folder,
                parent=None
            )

            if layer_dict:
                path = list(layer_dict.values())[0]
                layer = QgsVectorLayer(path, label, "ogr")
                if layer.isValid():
                    return layer

        self.iface.messageBar().pushWarning(
            "Erreur",
            self.config["messages"]["layer_not_found"]
        )
        return None


    # ---------------------------------------------------------
    # Résolution couche
    # ---------------------------------------------------------
    def _resolve_layer(self, shapefile_path):

        if isinstance(shapefile_path, QgsVectorLayer):
            if shapefile_path.isValid():
                return shapefile_path
            raise ValueError("Couche invalide")

        if isinstance(shapefile_path, str):
            layer = QgsVectorLayer(shapefile_path, "tmp_layer", "ogr")
            if layer.isValid():
                return layer

            project_layer = QgsProject.instance().mapLayer(shapefile_path)
            if project_layer and project_layer.isValid():
                return project_layer

            raise ValueError("Impossible de charger la couche")

        raise TypeError("Format de couche non supporté")
    
    # --------------------------------------------------------
    # Définition de la ville et du propriétaire
    # --------------------------------------------------------


    def _set_city_and_owner(self, parca_path):
        """
        Calcul City & Owner et stocke dans self._calculated_values pour sauvegarde ultérieure.
        """

        cfg = self.config["fields"]

        city = owner = ""
        if parca_path.isValid():

            layer = self._resolve_layer(parca_path)
            # --- Récupère le nom réel des champs ---
            city_field = self._resolve_field_name(layer, "com_name", json_fallback_key="city_field")
            city_filter = self._resolve_field_name(layer, "dep_code", json_fallback_key="city_filter")
            owner_field = self._resolve_field_name(layer, "owner", json_fallback_key="owner_field")
            surface_field = self._resolve_field_name(layer, "cad_area", json_fallback_key="surface_field_parca")

            city = self.get_grouped_values_from_shapefile(
                parca_path,
                city_field,
                city_filter,
                surface_field
            )
            owner = self.get_grouped_values_from_shapefile(
                parca_path,
                owner_field,
                None,
                surface_field
            )

        # Stockage interne pour export JSON
        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}
        self._calculated_values["city"] = city
        self._calculated_values["owner"] = owner


        if self._calculated_values:
            print("--_set_city_and_owner execution was succesfully--!")

        # Optionnel : garder les setters projet
        #set_project_variable("forest_city", city)
        #set_project_variable("forest_owner", owner)


    # --------------------------------------------------------
    # Définition des surfaces
    # --------------------------------------------------------

    def get_grouped_values_from_shapefile(self, shapefile_path, value_field, filter_field, surface_field, result_key=None):
        """
        Calcule les valeurs groupées à partir d'un QgsVectorLayer ou chemin de couche,
        stocke le résultat dans self._calculated_values pour JSON.
        """
        from collections import defaultdict
        layer = self._resolve_layer(shapefile_path)
        field_names = layer.fields().names()

        if value_field not in field_names or surface_field not in field_names:
            raise ValueError(f"Champ introuvable : {value_field} ou {surface_field}")

        if filter_field is not None and filter_field not in field_names:
            filter_field = None

        group_dict = defaultdict(list)

        for feat in layer.getFeatures():
            group = feat[filter_field] if filter_field else "No Filter"
            value = feat[value_field]
            surface = feat[surface_field] or 0.0
            if value is not None:
                group_dict[group].append((value, float(surface)))

        result_list = []

        for group, values in group_dict.items():
            aggregated_values = defaultdict(float)
            for value, surface in values:
                aggregated_values[value] += surface

            sorted_values = sorted(aggregated_values.items(), key=lambda x: x[1], reverse=True)
            value_list = [v[0] for v in sorted_values]

            if len(value_list) == 2:
                result_string = f"{value_list[0]} & {value_list[1]}"
            else:
                result_string = f"{', '.join(value_list[:-1])} & {value_list[-1]}" if len(value_list) > 1 else value_list[0]

            if group != "No Filter":
                result_list.append(f"{result_string} ({group})")
            else:
                result_list.append(result_string)

        final_result = "; ".join(result_list)

        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}
        self._calculated_values[result_key or "grouped_values"] = final_result

        if self._calculated_values:
            print("--get_grouped_values_from_shapefile execution was succesfully--!")

        return final_result
    

    def sum_surface_from_shapefile(self, shapefile_path, surface_field, filter_field=None, filter_value=None, result_key=None):
        """
        Calcule la somme des surfaces à partir d'un QgsVectorLayer ou chemin de couche,
        stocke le résultat dans self._calculated_values pour JSON.
        """
        layer = self._resolve_layer(shapefile_path)
        field_names = layer.fields().names()

        if surface_field not in field_names:
            raise ValueError(f"Champ introuvable : {surface_field}")
        if filter_field and filter_field not in field_names:
            filter_field = None

        total_surface = 0.0

        for feat in layer.getFeatures():
            if filter_field and filter_value is not None:
                if feat[filter_field] != filter_value:
                    continue
            total_surface += float(feat[surface_field] or 0.0)

        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}
        self._calculated_values[result_key or "total_surface"] = total_surface

        if self._calculated_values:
            print("--sum_surface_from_shapefile execution was succesfully--!")

        return total_surface



    def _set_surface(self, ua_path, parca_path):
        """
        Calcul des surfaces et stockage dans self._calculated_values.
        """

        cfg = self.config["fields"]

        if not ua_path.isValid() and not parca_path.isValid():
            raise FileNotFoundError(
                self.config["messages"]["layers_missing"].format(directory=self.directory)
            )

        surface_field = cfg["surface_field_ua"] if ua_path.isValid() else cfg["surface_field_parca"]
        path = ua_path if ua_path.isValid() else parca_path

        surface_boisee = self.sum_surface_from_shapefile(
            path, surface_field, cfg["occup_field"], cfg["surface_boisee"]
        ) or 0

        surface_non_boisee = self.sum_surface_from_shapefile(
            path, surface_field, cfg["occup_field"], cfg["surface_non_boisee"]
        ) or 0

        surface_totale = surface_boisee + surface_non_boisee

        # Stockage interne pour export JSON plus tard
        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}
        self._calculated_values["surface_boisee_m2"] = surface_boisee
        self._calculated_values["surface_non_boisee_m2"] = surface_non_boisee
        self._calculated_values["surface_totale_m2"] = surface_totale

        # Optionnel : variables projet
        #set_project_variable("forest_surface_boisee", surface_boisee)
        #set_project_variable("forest_surface_non_boisee", surface_non_boisee)
        #set_project_variable("forest_surface_totale", surface_totale)
        if self._calculated_values:
            print("--_set_surface execution was succesfully--!")




    # ---------------------------------------------------------
    # Agrégation dynamique
    # ---------------------------------------------------------
    def get_grouped_values(self, shapefile_path=None):
        """
        Retourne la surface totale par commune sous forme de chaîne formatée
        respectant les séparateurs du JSON.
        """

        if shapefile_path is None:
            shapefile_path = self.layer

        layer = self._resolve_layer(shapefile_path)

        cfg_fields = self.config["fields"]
        cfg_format = self.config["formatting"]
        cfg_surface = self.config["surface"]

        filter_field = cfg_fields["filter_field"]
        surface_field = cfg_fields["surface_field"]
        surface_fallback = cfg_fields["surface_fallback"]
        no_filter_label = cfg_surface["no_filter_label"]

        field_names = [f.name() for f in layer.fields()]

        # fallback si champ introuvable
        if surface_field not in field_names and surface_fallback in field_names:
            surface_field = surface_fallback

        if filter_field not in field_names or surface_field not in field_names:
            raise ValueError(f"{self.config['messages']['invalid_field']} : {filter_field}, {surface_field}")

        # -------------------------------
        # Dictionnaire regroupement
        # -------------------------------
        group_dict = defaultdict(float)  # juste float pour stocker surface

        for feat in layer.getFeatures():
            commune = feat[filter_field] if filter_field != no_filter_label else no_filter_label
            surface = float(feat[surface_field] or 0.0)
            group_dict[commune] += surface

        # -------------------------------
        # Construction de la chaîne finale
        # -------------------------------
        result_list = []
        for commune, total_surface in group_dict.items():
            result_list.append(f"{commune} ({total_surface})")

        return cfg_format["group_separator"].join(result_list)

    # ---------------------------------------------------------
    # Somme surface configurable
    # ---------------------------------------------------------
    def sum_surface(self, shapefile_path=None, filter_field=None, filter_value=None):

        if shapefile_path is None:
            shapefile_path = self.layer

        layer = self._resolve_layer(shapefile_path)

        cfg_fields = self.config["fields"]
        cfg_surface = self.config["surface"]

        surface_field = cfg_fields["surface_field"]
        surface_fallback = cfg_fields["surface_fallback"]
        null_value = cfg_surface["null_value"]

        field_names = layer.fields().names()

        # --- fallback surface ---
        if surface_field not in field_names and surface_fallback in field_names:
            surface_field = surface_fallback

        # --- validations ---
        if surface_field not in field_names:
            raise ValueError(
                f"{self.config['messages']['invalid_field']} : {surface_field}"
            )

        if filter_field and filter_field not in field_names:
            raise ValueError(
                f"{self.config['messages']['invalid_field']} : {filter_field}"
            )

        # -----------------------------------------------------
        # CAS 1 : filtre actif
        # -----------------------------------------------------
        if filter_field and filter_value is not None:

            total = 0.0

            for feat in layer.getFeatures():
                if feat[filter_field] == filter_value:
                    v = feat[surface_field]
                    total += float(v) if v is not None else null_value

            return total

        # -----------------------------------------------------
        # CAS 2 : somme globale
        # -----------------------------------------------------
        if filter_field is None or filter_value is None:

            total_surface = 0.0

            for feat in layer.getFeatures():
                v = feat[surface_field]
                total_surface += float(v) if v is not None else null_value

            return total_surface

        # -----------------------------------------------------
        # PARTIE théorique
        # Jamais atteinte mais conservée volontairement
        # -----------------------------------------------------
        surface_by_group = defaultdict(float)

        for feat in layer.getFeatures():
            k = feat[filter_field]
            v = feat[surface_field]
            surface_by_group[k] += float(v) if v is not None else null_value

        if filter_value in surface_by_group:
            return surface_by_group[filter_value]
        else:
            return None


    # ---------------------------------------------------------
    # Formatage surface
    # ---------------------------------------------------------
    def get_formated_surface(self, surface_boisee, surface_non_boisee):

        cfg = self.config["surface"]

        divider = cfg["unit_divider"]
        decimals = cfg["round_decimals"]

        surface_totale = surface_boisee + surface_non_boisee

        # -------------------------------
        # CAS 1 : surface non boisée > 0
        # -------------------------------
        if surface_non_boisee > 0:

            surface_totale_ha = round(surface_totale / divider, decimals)
            surface_boisee_ha = round(surface_boisee / divider, decimals)

            formatted_surface = (
                f"{cfg['text_total']} {surface_totale_ha:.{decimals}f} {cfg['ha_label']} | "
                f"{cfg['text_boisee']} {surface_boisee_ha:.{decimals}f} {cfg['ha_label']}"
            )

        # -------------------------------
        # CAS 2 : uniquement surface boisée
        # -------------------------------
        else:

            hectares = int(surface_boisee // divider)
            ares = int((surface_boisee % divider) // 100)
            centiares = int(surface_boisee % 100)

            formatted_surface = (
                f"{cfg['text_total']} "
                f"{hectares} {cfg['ha_label']} "
                f"{ares:02} {cfg['a_label']} "
                f"{centiares:02} {cfg['ca_label']}"
            )

        return formatted_surface
    
    # ---------------------------------------------------------
    # Sauvegarde et export complet dans un JSON
    # ---------------------------------------------------------

    def run_all_calculations(self):
        parca_layer = self._find_layer("PARCA")
        ua_layer = self._find_layer("UA")

        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}

        # Ville et propriétaire (PARCA)
        if parca_layer:
            self._set_city_and_owner(parca_layer)

        # Surfaces (UA si dispo, sinon fallback sur PARCA)
        if ua_layer or parca_layer:
            self._set_surface(ua_layer if ua_layer else None, parca_layer if parca_layer else None)
            surface_boisee = self._calculated_values.get("surface_boisee_m2", 0.0)
            surface_non_boisee = self._calculated_values.get("surface_non_boisee_m2", 0.0)
        else:
            surface_boisee = surface_non_boisee = 0.0

        # -------------------------------
        # 3. Regroupements et somme globale
        # -------------------------------
        grouped_values = self.get_grouped_values()
        total_surface = self.sum_surface()

        self._calculated_values["grouped_values"] = grouped_values
        self._calculated_values["total_surface_m2"] = total_surface
        self._calculated_values["surface_formatted"] = self.get_formated_surface(
            surface_boisee, surface_non_boisee
        )

        # -------------------------------
        # 4. Export JSON
        # -------------------------------
        self.export_all_to_json()



    def export_all_to_json(self):
        """
        Exporte tous les résultats calculés et la config complète dans un JSON.
        Écrase le fichier existant.
        """

        # Chemin par défaut si non fourni
        file_path = os.path.join(self.script_dir,"..", "..","data","_metadata","currentFolder","forest_metadata.json")
        if file_path is None:
            file_path = self.results_path

        data_to_save = {
            "project_name": self.project_name,
            "project_folder": self.project_folder,
            "style_folder": self.style_folder,
            "timestamp": datetime.now().isoformat(),
            "metadata": getattr(self, "_calculated_values", {})  # Résultats calculés
            }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            print(f"Données exportées dans {file_path}")
        except Exception as e:
            print(f"Erreur lors de l'export JSON : {e}")
