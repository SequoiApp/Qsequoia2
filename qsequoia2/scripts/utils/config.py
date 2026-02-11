# region IMPORT


"""
Module `config.py` : gestion des chemins, structure SIG, projets, styles et WMTS.

Ce module fournit des fonctions pour :
- récupérer le dossier du plugin et des fichiers de configuration
- lire la structure SIG (`sig_structure.yaml`)
- rechercher des couches vecteur ou raster dans un dossier de projet
- récupérer les styles (.qml)
- accéder aux projets et layouts
- récupérer les services WMTS
"""

from qgis.core import (QgsMessageLog,Qgis)
import os
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

# region SIG_STRUCTURE

_SIG_STRUCT: dict | None = None

def _load_sig_structure() -> dict:
    """
    Charge le fichier sig_structure.yaml en mémoire et le met en cache.
    
    Returns:
        dict: structure SIG
    """

    global _SIG_STRUCT
    if _SIG_STRUCT is None:
        cfg_path = get_config_path("sig_structure.yaml")
        with open(cfg_path, encoding="utf-8") as f:
            _SIG_STRUCT = yaml.safe_load(f)
    return _SIG_STRUCT

def _find_entry(logical_key):
    """
    Retourne l'entrée correspondante à une clé logique dans la structure SIG.

    Args:
        logical_key (str): clé logique à rechercher

    Returns:
        tuple: (entry_dict, folder_path_parts)
    
    Raises:
        KeyError: si la clé n'existe pas
    """

    struct = _load_sig_structure()["structure"]
    if logical_key in struct.keys():
        path = struct[logical_key].get("path", [])
        return False, path  
    for folder in struct.values():
        files = folder.get("files", {})
        if logical_key in files:
            return files[logical_key], folder.get("path", [])
    raise KeyError(f"No entry for '{logical_key}' in sig_structure.yaml")


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

def find_best_layer_qgis(project_folder, label, max_candidates=3):
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

    expected_geom = None
    if parts[-1] in ("poly", "line", "point"):
        expected_geom = parts[-1]
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

            score = 0

            # --- Détection vecteur
            if fname.endswith(vector_exts):
                if expected_geom and expected_geom in fname:
                    score += 50
                for token in expected_tokens:
                    if token in fname:
                        score += 20
                if score > 0:
                    candidates.append((score, path))

            # --- Détection raster
            elif fname.endswith(raster_exts):
                # Pour raster, on ne teste pas la géométrie
                # juste les tokens métier
                for token in expected_tokens:
                    if token in fname:
                        score += 20
                if score > 0:
                    candidates.append((score, path))

    if not candidates:
        return None

    # On garde les N meilleurs
    candidates.sort(reverse=True)
    candidates = candidates[:max_candidates]

    # ----------------------------
    # Vérification finale
    # ----------------------------
    for _, path in candidates:
        if path.lower().endswith(vector_exts):
            # vecteur → vérification géométrie
            layer = QgsVectorLayer(path, "tmp", "ogr")
            if not layer.isValid():
                continue
            g = QgsWkbTypes.geometryType(layer.wkbType())
            found_geom = None
            if g == QgsWkbTypes.PolygonGeometry:
                found_geom = "poly"
            elif g == QgsWkbTypes.LineGeometry:
                found_geom = "line"
            elif g == QgsWkbTypes.PointGeometry:
                found_geom = "point"
            if expected_geom and found_geom != expected_geom:
                continue
            return path

        elif path.lower().endswith(raster_exts):
            # raster → on accepte directement
            return path

    return None



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

    # --- Extraire token métier + type de géométrie (vecteur)
    parts = label.split("_")
    geom = ""
    if len(parts) >= 2 and parts[-1] in ("poly", "line", "point"):
        geom = parts[-1]
        token = parts[1]
        token_with_geom = f"{token}_{geom}"
    elif len(parts) >= 2:
        token = parts[1]
        token_with_geom = token
    else:
        token = label_lower
        token_with_geom = token


    token_with_geom = token_with_geom.lower()
    token = token.lower()  # pour fallback

    # --- Scan des fichiers QML
    if not os.path.isdir(style_folder):
        return None

    # --- Liste des fichiers QML
    qml_files = [f for f in os.listdir(style_folder) if f.lower().endswith(".qml")]

    best_match = None

    # Cherche un match exact token + geom (vecteur)
    for f in qml_files:
        fname = os.path.splitext(f)[0].lower()
        if token_with_geom in fname:
            best_match = os.path.join(style_folder, f)
            break

    # Si pas trouvé, match sur token seul (vecteur ou raster)
    if not best_match:
        for f in qml_files:
            fname = os.path.splitext(f)[0].lower()
            if token in fname:
                best_match = os.path.join(style_folder, f)
                break

    # Si toujours pas trouvé, pour raster on peut tester juste label complet
    if not best_match and not geom:
        for f in qml_files:
            fname = os.path.splitext(f)[0].lower()
            if label_lower in fname:
                best_match = os.path.join(style_folder, f)
                break

    return best_match


    
    

#endregion









def get_display_name(logical_key):
    """
    Retourne le nom d'affichage pour une clé logique SIG.

    Args:
        logical_key (str): clé logique

    Returns:
        str: nom d'affichage ou la clé elle-même si non défini
    """
    entry, _ = _find_entry(logical_key)
    return entry.get("display_name")

def get_project(folder: str = "output_folder"):

    """
    Retourne un dictionnaire des noms de projets disponibles pour un dossier donné.

    Args:
        folder (str): nom du dossier dans sig_structure.yaml

    Returns:
        dict: {clé: display_name}
    """

    structure = _load_sig_structure()["structure"]

    if folder not in structure:
        raise KeyError(f"Dossier '{folder}' non trouvé dans sig_structure.yaml")

    files = structure[folder]["files"]
    project_names = {key: get_display_name(key) for key in files.keys()}

    return project_names
  
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


