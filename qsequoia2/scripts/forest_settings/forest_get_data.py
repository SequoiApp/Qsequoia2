""""""

# region import

from collections import defaultdict

import importlib
from PyQt5.QtWidgets import QDialog, QMessageBox, QFileDialog

from qgis.core import (
    QgsVectorLayer,
    QgsProject,
)


from ..utils.config import get_path

import os




class getForestdata():
    """Classe getForestdata : récupération d'information dans les couches"""

    def __init__(self, project_name, project_folder, style_folder,iface):

        self.project_name = project_name
        self.project_folder = project_folder
        self.style_folder = style_folder

        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.json_path = os.path.join(self.script_dir, "forest_data.json")


        layer_dict = get_path(
            label='SEQ_PARCA_poly',
            project_name=self.project_name,
            project_folder=self.project_folder,
            style_folder=self.style_folder,
            parent=None
        )


        self.shapefile_path = list(layer_dict.values())[0] if layer_dict else None

    # ------------------------------------------------------------------
    # Helper interne : accepte QgsVectorLayer OU URI/chemin -> QgsVectorLayer
    # ------------------------------------------------------------------
    def _resolve_layer(self, shapefile_path):
        """
        Ne change pas le nom 'shapefile_path' mais accepte :
          - QgsVectorLayer
          - str : chemin/URI (gpkg, postgis, wfs, etc.)
        Retourne un QgsVectorLayer valide, sinon lève une exception.
        """

        # Cas 1 : déjà une couche
        if isinstance(shapefile_path, QgsVectorLayer):
            layer = shapefile_path
            if not layer.isValid():
                raise ValueError("Couche invalide (QgsVectorLayer fourni mais non valide).")
            return layer

        # Cas 2 : une chaîne (chemin/URI)
        if isinstance(shapefile_path, str):
            # On tente de charger via OGR (fonctionne pour shp/gpkg/geojson…)
            layer = QgsVectorLayer(shapefile_path, "tmp_layer", "ogr")

            # Si OGR échoue, on peut tenter de récupérer une couche déjà chargée
            if not layer.isValid():
                # Essai : considérer que shapefile_path est un layer ID dans le projet
                project_layer = QgsProject.instance().mapLayer(shapefile_path)
                if isinstance(project_layer, QgsVectorLayer) and project_layer.isValid():
                    return project_layer

                raise ValueError(f"Impossible de charger la couche depuis : {shapefile_path}")

            return layer

        raise TypeError("shapefile_path doit être un QgsVectorLayer ou une URI/chemin (str).")

    # ------------------------------------------------------------------
    # Fonction pour City & Owner (PyQGIS)
    # ------------------------------------------------------------------
    def get_grouped_values_from_shapefile(self, shapefile_path, value_field, filter_field, surface_field):
        layer = self._resolve_layer(shapefile_path)

        fields = layer.fields()
        field_names = fields.names()

        # --- fallback SURF_CAD -> SURF_CA ---
        if surface_field == "SURF_CAD" and "SURF_CAD" not in field_names and "SURF_CA" in field_names:
            surface_field = "SURF_CA"

        # validations
        if value_field not in field_names:
            raise ValueError(f"Champ '{value_field}' introuvable dans la couche.")
        if filter_field is not None and filter_field != "No Filter" and filter_field not in field_names:
            raise ValueError(f"Champ '{filter_field}' introuvable dans la couche.")
        if surface_field not in field_names:
            raise ValueError(f"Champ '{surface_field}' introuvable dans la couche.")

        # Dictionnaire pour regrouper les valeurs
        group_dict = defaultdict(list)

        # Si filter_field est None, on va regrouper sous un groupe "No Filter"
        if filter_field is None:
            filter_field = "No Filter"

        # Vérifications simples des champs (si ce n'est pas "No Filter")
        fields = layer.fields()
        if value_field not in fields.names():
            raise ValueError(f"Champ '{value_field}' introuvable dans la couche.")
        if surface_field not in fields.names():
            raise ValueError(f"Champ '{surface_field}' introuvable dans la couche.")
        if filter_field != "No Filter" and filter_field not in fields.names():
            raise ValueError(f"Champ '{filter_field}' introuvable dans la couche.")

        # Parcours des entités
        for feat in layer.getFeatures():
            # Si filter_field est "No Filter", on n'utilise pas de champ de filtre
            filter_value = feat[filter_field] if filter_field != "No Filter" else "No Filter"
            value = feat[value_field]
            surface = feat[surface_field]

            # Sécurités (valeurs nulles)
            if value is None:
                continue
            if surface is None:
                surface = 0.0

            # Regroupement des valeurs par le champ de filtre
            group_dict[filter_value].append((value, float(surface)))

        result_list = []

        # Pour chaque groupe, on agrège les valeurs
        for group, values in group_dict.items():
            aggregated_values = defaultdict(float)

            for value, surface in values:
                aggregated_values[value] += surface

            # Trie en fonction de la somme des surfaces
            sorted_values = sorted(aggregated_values.items(), key=lambda x: x[1], reverse=True)
            value_list = [v[0] for v in sorted_values]

            # Construction de la chaîne avec ", " et "&"
            if len(value_list) == 0:
                continue
            if len(value_list) == 2:
                result_string = f"{value_list[0]} & {value_list[1]}"
            else:
                result_string = f"{', '.join(value_list[:-1])} & {value_list[-1]}" if len(value_list) > 1 else str(value_list[0])

            # Si filter_field était None au départ, on ne veut pas afficher "(No Filter)"
            if filter_field != "No Filter":
                result_list.append(f"{result_string} ({group})")
            else:
                result_list.append(f"{result_string}")

        return "; ".join(result_list)

    # ------------------------------------------------------------------
    # Fonction pour Surface (PyQGIS)
    # ------------------------------------------------------------------
    def sum_surface_from_shapefile(self, shapefile_path, surface_field, filter_field=None, filter_value=None):
        layer = self._resolve_layer(shapefile_path)

        field_names = layer.fields().names()

        # --- fallback SURF_CAD -> SURF_CA ---
        if surface_field == "SURF_CAD" and "SURF_CAD" not in field_names and "SURF_CA" in field_names:
            surface_field = "SURF_CA"

        if surface_field not in field_names:
            raise ValueError(f"Champ '{surface_field}' introuvable dans la couche.")
        if filter_field and filter_field not in field_names:
            raise ValueError(f"Champ '{filter_field}' introuvable dans la couche.")


        # Si un filter_field et un filter_value sont spécifiés, on filtre les entités
        # (comportement fidèle à ton code d'origine)
        if filter_field and filter_value is not None:
            total = 0.0
            for feat in layer.getFeatures():
                if feat[filter_field] == filter_value:
                    v = feat[surface_field]
                    total += float(v) if v is not None else 0.0
            return total

        # Si filter_field est None ou si aucun filtre n'est appliqué, somme globale
        if filter_field is None or filter_value is None:
            total_surface = 0.0
            for feat in layer.getFeatures():
                v = feat[surface_field]
                total_surface += float(v) if v is not None else 0.0
            return total_surface

        # --- NOTE ---
        # Cette partie n'est jamais atteinte avec la logique ci-dessus
        # (car si filter_value est None, on retourne déjà la somme globale).
        # Je la garde conceptuellement fidèle, mais elle restera inutilisée.

        surface_by_group = defaultdict(float)
        for feat in layer.getFeatures():
            k = feat[filter_field]
            v = feat[surface_field]
            surface_by_group[k] += float(v) if v is not None else 0.0

        if filter_value in surface_by_group:
            return surface_by_group[filter_value]
        else:
            return None

    # ------------------------------------------------------------------
    # Formatage surface (inchangé, pur Python)
    # ------------------------------------------------------------------
    def get_formated_surface(self, surface_boisee, surface_non_boisee):
        surface_totale = surface_boisee + surface_non_boisee

        if surface_non_boisee > 0:
            surface_totale_ha = round(surface_totale / 10000, 4)
            surface_boisee_ha = round(surface_boisee / 10000, 4)
            formatted_surface = (
                f"Surface totale: {surface_totale_ha:.4f} ha | Surface boisée: {surface_boisee_ha:.4f} ha"
            )
        else:
            hectares = round(surface_boisee // 10000)
            ares = round((surface_boisee % 10000) // 100)
            centiares = round(surface_boisee % 100)
            formatted_surface = (
                f"Surface totale: {hectares} ha {ares:02} a {centiares:02} ca"
            )

        return formatted_surface