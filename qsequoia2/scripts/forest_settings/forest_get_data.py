"""
Classe getForestdata

Cette classe centralise la lecture, le traitement et l'agrégation
des données forestières à partir des couches SIG (PARCA et UA)
dans QGIS. 

Fonctionnalités principales :
- Résolution dynamique des champs via YAML et JSON (noms et alias)
- Sélection intelligente de la couche et du champ surface (UA prioritaire)
- Calcul des surfaces boisées et non boisées
- Agrégation par commune et par propriétaire
- Génération de chaînes formatées pour affichage
- Export complet des résultats et métadonnées vers un fichier JSON

Utilisation typique :
1. Instanciation avec le projet QGIS et chemins des dossiers.
2. Exécution de `run_all_calculations()` pour calculer et stocker toutes les valeurs.
3. Récupération des résultats dans `self._calculated_values` ou export via JSON.


Auteur : Alexandre Le Bars - Comité des Forêts, Paul Carteron - Racine experts forestiers associés

alexlb329@gmail.com

Ce programme est sous licence SequoiAPP l'utilisation hors Qsequoia2 est soumis à autorisation
"""

# region import
#====================================================
# Import
#====================================================

import os, yaml, glob, json
from collections import defaultdict
from qgis.core import QgsVectorLayer, QgsProject, QgsField
from PyQt5.QtCore import QVariant
from ..utils.config import *
from datetime import datetime
from qgis.PyQt.QtWidgets import QMessageBox,QFileDialog, QInputDialog, QListWidget, QScrollArea

# endregion

#===================================================
# region getForestdata
#===================================================


class getForestdata:
    """Lecture depuis une couche PARCA des donénes sur la forêt. 
        Paramètre lu depuis la table forest_setting_data.json"""

    def __init__(self, project_name, project_folder, style_folder, iface):
        """Initialise l’objet getForestdata.
            Charge la configuration JSON et YAML, résout les définitions de champs,
            récupère les couches du projet et prépare la structure interne
            pour stocker les valeurs calculées destinées à l’export JSON.
        """

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
        """
        Résout dynamiquement le nom réel d’un champ dans une couche.

        Recherche d’abord via la définition YAML (nom + alias),
        puis applique un fallback éventuel défini dans le JSON.
        Lève une erreur si aucun champ valide n’est trouvé.
        """
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
                self.iface.messageBar().pushMessage(f" Champ '{json_fallback_key}' fallback JSON introuvable dans la couche.", Qgis.Warning)
                return fallback_name
        raise ValueError(f"Aucun champ trouvé pour '{field_key}' dans la couche. Cherché: {possible_names}")

    # ---------------------------------------------------------
    # Recherche couche selon type
    # ---------------------------------------------------------
    def _find_layer(self, layer_type="PARCA"):
        """
        Recherche et charge la première couche valide correspondant
        au type demandé (ex: PARCA ou UA) selon la configuration JSON.

        Retourne un QgsVectorLayer valide ou None si introuvable.
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
        """
        Résout une couche à partir d’un QgsVectorLayer existant
        ou d’un chemin vers un fichier.

        Retourne un QgsVectorLayer valide.
        Lève une erreur si la couche ne peut pas être chargée.
        """

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
        Calcule les surfaces par commune et par propriétaire
        à partir de la couche PARCA.

        Produit :
        - Une liste détaillée des communes et propriétaires (pour JSON)
        - Une version formatée en chaîne pour affichage rapide

        Les résultats sont stockés dans self._calculated_values.
        """

        if not parca_path.isValid():
            return

        layer = self._resolve_layer(parca_path)
        city_field = self._resolve_field_name(layer, "com_name", json_fallback_key="city_field")
        owner_field = self._resolve_field_name(layer, "owner", json_fallback_key="owner_field")
        surface_field = self._resolve_field_name(layer, "cad_area", json_fallback_key="surface_field_parca")

        # dictionnaires intermédiaires
        city_dict = defaultdict(float)
        owner_dict = defaultdict(lambda: {"commune": "", "surface_ha": 0.0})

        for feat in layer.getFeatures():
            commune = feat[city_field]
            owner = feat[owner_field]
            surface = float(feat[surface_field] or 0.0)

            city_dict[commune] += surface
            if owner:
                owner_dict[(commune, owner)]["commune"] = commune
                owner_dict[(commune, owner)]["surface_ha"] += surface

        # --- Listes détaillées pour JSON ---
        city_list = [{"commune": k, "surface_ha": v} for k, v in city_dict.items()]
        owner_list = [{"commune": k[0], "owner": k[1], "surface_ha": v["surface_ha"]} for k, v in owner_dict.items()]

        # --- Chaînes “mise en forme” ---
        cfg_format = self.config["formatting"]

        # City string
        city_values = [f"{c['commune']} ({c['surface_ha']:.4f} ha)" for c in city_list] #:.4f = 4 décimals
        city_str = (
            f"{cfg_format['separator'].join(city_values[:-1])}{cfg_format['last_separator']}{city_values[-1]}"
            if len(city_values) > 1 else city_values[0])

        # Owner string (concat par commune, si plusieurs)
        owner_values = list(dict.fromkeys(o["owner"] for o in owner_list))

        owner_str = (
            f"{cfg_format['separator'].join(owner_values[:-1])}"
            f"{cfg_format['last_separator']}{owner_values[-1]}"
            if len(owner_values) > 1 else owner_values[0])


        # Stockage interne pour export JSON
        self._calculated_values["city_list"] = city_list
        self._calculated_values["owner_list"] = owner_list
        self._calculated_values["city_str"] = city_str
        self._calculated_values["owner_str"] = owner_str


    # --------------------------------------------------------
    # Définition des surfaces
    # --------------------------------------------------------

    def get_grouped_values_from_shapefile(self, shapefile_path, value_field, filter_field, surface_field, result_key=None):
        """
        Agrège des valeurs par groupe à partir d’une couche.

        Regroupe les surfaces selon un champ de valeur
        et un éventuel champ de filtre.

        Retourne une chaîne formatée et stocke le résultat
        dans self._calculated_values pour export JSON.
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

        return final_result
    

    def sum_surface_from_shapefile(self, shapefile_path, surface_field_key, filter_field_key=None, filter_value=None, result_key=None):
        """
        Calcule la somme des surfaces d’une couche.

        Peut appliquer un filtre facultatif sur un champ donné.
        Résout dynamiquement les noms réels des champs.

        Stocke le résultat dans self._calculated_values.
        """
        layer = self._resolve_layer(shapefile_path)

        # résolution des noms réels
        surface_field = self._resolve_field_name(layer, surface_field_key, json_fallback_key="surface_field_parca")
        filter_field = self._resolve_field_name(layer, filter_field_key, json_fallback_key=None) if filter_field_key else None

        total_surface = 0.0
        for feat in layer.getFeatures():
            if filter_field and filter_value is not None:
                if feat[filter_field] != filter_value:
                    continue
            total_surface += float(feat[surface_field] or 0.0)

        if not hasattr(self, "_calculated_values"):
            self._calculated_values = {}
        self._calculated_values[result_key or "total_surface"] = total_surface

        return total_surface


    def _set_surface(self, ua_layer, parca_layer):
        """
        Calcule les surfaces boisée, non boisée et totale.

        - Priorité à UA si SURF_COR est exploitable
        - Sinon fallback automatique vers PARCA
        - Détermine le caractère boisé via configuration YAML/JSON
        - Stocke les surfaces calculées et formatées dans self._calculated_values
        """

        cfg = self.config["fields"]

        # ---------------------------------------------------------
        # Choix intelligent de la couche et du champ surface
        # ---------------------------------------------------------
        layer = None
        surface_field = None

        # Test UA avec SURF_COR
        if ua_layer and ua_layer.isValid():
            ua_field = cfg.get("surface_field_ua")
            if ua_field in ua_layer.fields().names():
                surfaces = [float(feat[ua_field] or 0.0) for feat in ua_layer.getFeatures()]
                total_ua = sum(surfaces)
                unique_values = set(surfaces)
                if total_ua > 0 and len(unique_values) > 1:
                    layer = ua_layer
                    surface_field = ua_field

        # Fallback PARCA
        if layer is None and parca_layer and parca_layer.isValid():
            for field_name in [cfg.get("surface_field"), cfg.get("surface_fallback")]:
                if field_name in parca_layer.fields().names():
                    total_parca = sum(float(feat[field_name] or 0.0) for feat in parca_layer.getFeatures())
                    if total_parca > 0:
                        layer = parca_layer
                        surface_field = field_name
                        break

        if layer is None or surface_field is None:
            self.iface.messageBar().pushMessage(
                "Attention : aucune surface exploitable trouvée",
                Qgis.Warning
            )
            return

        # ---------------------------------------------------------
        # Détermination du champ "boisé"
        # ---------------------------------------------------------
        occup_field = None
        if layer == ua_layer:
            try:
                occup_field = self._resolve_field_name(layer, "is_wooded", json_fallback_key="occup_field")
            except ValueError:
                # UA mais absent → création temporaire
                temp_field_name = "OCCUP_SOL"
                if temp_field_name not in [f.name() for f in layer.fields()]:
                    layer.startEditing()
                    layer.dataProvider().addAttributes([QgsField(temp_field_name, QVariant.Bool)])
                    layer.updateFields()
                    layer.commitChanges()
                occup_field = temp_field_name
                self.iface.messageBar().pushMessage(
                    "Champ boisé temporaire créé pour UA, toutes les entités considérées comme boisées.",
                    level=Qgis.Success,
                    duration=10
                )

            # Remplir le champ temporaire
            layer.startEditing()
            for feat in layer.getFeatures():
                feat[occup_field] = True
                layer.updateFeature(feat)
            layer.commitChanges()

        # ---------------------------------------------------------
        # Calcul des surfaces
        # ---------------------------------------------------------
        surface_boisee = 0.0
        surface_non_boisee = 0.0
        city_dict = defaultdict(lambda: {"boisee": 0.0, "non_boisee": 0.0})

        for feat in layer.getFeatures():
            surface = float(feat[surface_field] or 0.0)
            commune = feat[cfg.get("filter_field")] if cfg.get("filter_field") in layer.fields().names() else "No Filter"

            if layer == ua_layer and occup_field:
                is_wooded_value = feat[occup_field]
                if is_wooded_value in [True, 1, "1", "True", "true","vrai","BOISEE","NR","nr",""]:
                    surface_boisee += surface
                    city_dict[commune]["boisee"] += surface
                else:
                    surface_non_boisee += surface
                    city_dict[commune]["non_boisee"] += surface
            else:
                # PARCA ou UA sans champ → tout boisé
                surface_boisee += surface
                city_dict[commune]["boisee"] += surface

        surface_totale = surface_boisee + surface_non_boisee

        # ---------------------------------------------------------
        # Stockage interne pour export JSON
        # ---------------------------------------------------------
        self._calculated_values["surface_boisee_ha"] = surface_boisee
        self._calculated_values["surface_non_boisee_ha"] = surface_non_boisee
        self._calculated_values["surface_totale_ha"] = surface_totale
        self._calculated_values["surface_formatted"] = self.get_formated_surface(surface_boisee, surface_non_boisee)

    # ---------------------------------------------------------
    # Agrégation dynamique
    # ---------------------------------------------------------
    def get_grouped_values(self, shapefile_path=None):
        """
        Calcule la somme des surfaces d’une couche.

        Peut fonctionner :
        - En somme globale
        - Avec filtre sur un champ spécifique

        Applique les fallbacks de champs définis dans la configuration.
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
    
    # ---------------------------------------------------------
    # Sauvegarde et export complet dans un JSON
    # ---------------------------------------------------------

    def run_all_calculations(self):
        """
        Exécute l’ensemble des calculs métier.

        Enchaîne :
        - Ville et propriétaire
        - Surfaces
        - Regroupements
        - Export final vers JSON

        Centralise toute la logique de traitement.
        """
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
            surface_boisee = self._calculated_values.get("surface_boisee_ha", 0.0)
            surface_non_boisee = self._calculated_values.get("surface_non_boisee_ha", 0.0)
        else:
            surface_boisee = surface_non_boisee = 0.0

        # -------------------------------
        # 3. Regroupements et somme globale
        # -------------------------------
        grouped_values = self.get_grouped_values(ua_layer if ua_layer else parca_layer)
        total_surface = self._calculated_values.get("surface_totale_ha", 0.0)

        self._calculated_values["grouped_values"] = grouped_values
        self._calculated_values["total_surface_ha"] = total_surface

        # -------------------------------
        # 4. Export JSON
        # -------------------------------
        self.export_all_to_json()



    def export_all_to_json(self):
        """
        Exporte l’ensemble des données calculées
        dans le fichier forest_metadata.json.

        Écrase le fichier existant.
        Inclut les métadonnées projet et les résultats calculés.
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
                print(f"-- metadata build pour {self.project_folder} --!")
        except Exception as e:
            self.iface.messageBar().pushMessage(f"Erreur lors de l'export JSON : {e}", Qgis.Warning)