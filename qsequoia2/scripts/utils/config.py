# region IMPORT


"""
Module `config.py` : gestion des chemins, structure SIG, projets, styles et WMTS.

Ce module fournit des fonctions pour :
- récupérer le dossier du plugin et des fichiers de configuration
- rechercher des couches vecteur ou raster dans un dossier de projet
- récupérer les styles (.qml)
- accéder aux projets et layouts
- récupérer les services WMTS
"""

from qgis.core import (QgsMessageLog,Qgis)
import os, re
import yaml
from pathlib import Path
from dataclasses import dataclass



from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsWkbTypes



# endregion


# region PLUGIN PATH

def get_plugin_root() -> Path:
    """
    Retourne le répertoire racine du plugin (deux niveaux au-dessus de ce fichier).

    Returns:
        Path: chemin du dossier racine du plugin
    """

    return Path(__file__).resolve().parent.parent

def get_config_path(filename: str) -> Path:
    """
    Retourne le chemin complet vers un fichier du dossier 'inst' du plugin.

    Args:
        filename (str): nom du fichier

    Returns:
        Path: chemin complet du fichier
    """
    return get_plugin_root() / ".." / "inst" / filename

# endregion

# region GET PATH


# ----------------------------------------------------------------------------------
# Fonction get_path modifiée pour rechercher la couche dans le dossier de projet
# ----------------------------------------------------------------------------------

def get_path(label, project_name, project_folder, style_folder, parent):
    """
    Recherche le chemin du fichier correspondant à un label YAML seq_layers dans le projet.

    Args:
        label (str): label de la couche (ex: 'SEQ_SSPF_poly')
        project_name (str): nom du projet courant
        project_folder (str): dossier racine du projet
        style_folder (str): dossier contenant les styles
        parent (QWidget): widget parent (optionnel)

    Returns:
        dict: {label: chemin_complet} ou {} si non trouvé
    """

    path = find_best_layer_qgis(project_folder, label)

    if path:
        QgsMessageLog.logMessage(
            f"Layer trouvé : {path}",
            "Qsequoia2",
            level=Qgis.Info
        )
        return {label: path}

    QgsMessageLog.logMessage(
        f"Aucune couche trouvée pour {label}",
        "Qsequoia2",
        level=Qgis.Warning
    )
    return {}


# Fonction utilitaire de get_path pour trouver les couches

def find_best_layer_qgis(project_folder, label):
    """
    Recherche optimisée d'une couche vectorielle ou raster dans le dossier projet.

    Supporte :
        - vecteurs : shp, gpkg, geojson
        - rasters : tif, img

    Args:
        project_folder (str): dossier du projet
        label (str): label YAML (ex: 'SEQ_PARCA_poly')
        max_candidates (int, optional): nombre max de fichiers candidats à vérifier

    Returns:
        str | None: chemin du fichier trouvé, ou None si aucun
    """

    label = label.lower()
    parts = label.split("_")
    
    print(parts)

    expected_geom = None
    if parts[-1] in ("poly", "line", "point"):

        expected_geom = parts[-1]
        if expected_geom == "polygon":
            expected_geom = "poly"
        parts = parts[:-1]

    expected_tokens = parts

    # Extensions supportées
    vector_exts = (".shp", ".gpkg", ".geojson")
    raster_exts = (".tif", ".img")

    candidates = []

    for root, _, files in os.walk(project_folder):
        for f in files:
            fname = f.lower()
            path = os.path.join(root, f)

            # --- Détection vecteur
            if fname.endswith(vector_exts):

                stem = os.path.splitext(fname)[0]

                file_tokens = stem.split("_")

                if file_tokens[-1] == expected_geom:
                    if all(t in file_tokens for t in expected_tokens):
                        candidates.append(path)
            
            # --- Détection raster
            elif fname.endswith(raster_exts):
                stem = os.path.splitext(fname)[0]
                file_tokens = stem.split("_")
                if all(t in file_tokens for t in expected_tokens):
                    candidates.append(path)

    if candidates:
        best = max(candidates, key=lambda p: len(os.path.splitext(os.path.basename(p))[0].split("_")))
        return best

    # ----------------------------
    # Vérification finale
    # ----------------------------
    for path in candidates:
        if path.lower().endswith(vector_exts):
            layer = QgsVectorLayer(path, "tmp", "ogr")
            if not layer.isValid():
                continue
            return path



# endregion

# region STYLES


# ----------------------------------------------------------------------------------
# Fonction get_style modifiée pour rechercher le style dans le dossier de styles
# ----------------------------------------------------------------------------------



def get_style(layer_path, style_folder):
    """
    Sélectionne le fichier de style (.qml) le plus approprié pour une couche vecteur ou raster.

    Args:
        layer_path (dict): {label: path}
        style_folder (str): dossier contenant les fichiers .qml

    Returns:
        str | None: chemin du fichier de style correspondant
    """

    if not style_folder:
        raise ValueError("Global 'styles_directory' is not set")
    
    label, path = next(iter(layer_path.items()))
    label_lower = label.lower()
    parts = label_lower.split("_")

    geom = None
    token = None

    # --- Extraction token + geom
    if len(parts) >= 2 and parts[-1] in ("poly", "line", "point"):
        geom = parts[-1]
        token = parts[-2]   # <-- important : dernier mot métier
    elif len(parts) >= 2:
        token = parts[-1]
    else:
        token = label_lower

    # --- Vérif dossier
    if not os.path.isdir(style_folder):
        return None

    qml_files = [f for f in os.listdir(style_folder) if f.lower().endswith(".qml")]

    # --- Matching strict avec séparateurs
    def strict(pattern, fname):
        return re.search(rf"(^|[_\-]){pattern}($|[_\-])", fname)

    # ==================================================
    # 1. MATCH ULTRA PRIORITAIRE token + geom
    # ==================================================
    if geom:
        target = f"{token}_{geom}"
        for f in qml_files:
            fname = os.path.splitext(f)[0].lower()
            if strict(target, fname):
                return os.path.join(style_folder, f)

    # ==================================================
    # 2. MATCH token seul (fallback)
    # ==================================================
    for f in qml_files:
        fname = os.path.splitext(f)[0].lower()
        if strict(token, fname):
            return os.path.join(style_folder, f)

    return None

  
# endregion

# region WMTS

# -----------------------------------------------------------------------
# WMTS
# -----------------------------------------------------------------------

def get_wmts(logical_key):
    """
    Retourne le display_name et l'URL d'un service WMTS à partir de sa clé logique.

    Args:
        logical_key (str): clé logique ou display_name

    Returns:
        tuple: (display_name, url)
    
    Raises:
        KeyError: si le service n'est pas trouvé
    """

    wmts_config_path = get_config_path("qseq_URLS.yaml")
    with open(wmts_config_path, "r", encoding="utf-8") as f:
        wmts_config = yaml.safe_load(f)

    wmts_entries = wmts_config.get("wmts", {})

    # 1) Recherche directe par clé YAML
    entry = wmts_entries.get(logical_key)
    if entry:
        return entry.get("display_name"), entry.get("url")

    # 2) Recherche par display_name
    for key, data in wmts_entries.items():
        if data.get("display_name") == logical_key:
            return data.get("display_name"), data.get("url")

    # 3) Rien trouvé → erreur propre
    raise KeyError(f"No WMTS config for key or display_name '{logical_key}'")

# endregion


