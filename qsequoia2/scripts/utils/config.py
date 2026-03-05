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

def get_path(label, project_name, project_folder, style_folder, parent, layout_mode=None):
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

    # ==========================================
    # PATCH YAML anchors : label peut être une liste
    # ==========================================
    if isinstance(label, list):

        label = flatten(label)

        # flatten peut retourner une liste → on prend le premier élément
        if isinstance(label, list):
            label = label[0] if label else None

    # Sécurité
    if not isinstance(label, str):
        return {}

    path = find_best_layer_qgis(project_folder, label,layout_mode=layout_mode)

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

def find_best_layer_qgis(project_folder, label, layout_mode=None):
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


    # ==========================================
    # go trouver le chemin
    # ==========================================

    label = label.lower()
    parts = label.split("_")
    
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

        root_upper = root.upper()
        # Mode SIG : ignorer tout dossier LAYOUT
        if layout_mode == 1 and "LAYOUT" in root_upper:
            continue

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


# ==========================================================
# HELPERS
# ==========================================================

def flatten(label):
    """Transforme une liste imbriquée en liste simple"""
    result = []
    for x in label:
        if isinstance(x, list):
            result.extend(flatten(x))
        else:
            result.append(x)
    return result



# endregion

# region STYLES


# ----------------------------------------------------------------------------------
# Fonction get_style modifiée pour rechercher le style dans le dossier de styles
# ----------------------------------------------------------------------------------


# ---------------------------------------------------
# Préfixes projet (robuste avec ton YAML)
# ---------------------------------------------------
def get_project_prefixes():
    """
    Retourne la liste des préfixes projets depuis project.yaml.
    Supporte :
      - projects: [..]
      - OU projets = clés top-level (assemblage:, situation:, etc.)
    """
    yaml_path = os.path.join(os.path.dirname(__file__), "..", "..", "inst", "project.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    projects = cfg.get("projects")
    if isinstance(projects, list) and projects:
        return [str(p).upper() for p in projects]

    if isinstance(cfg, dict) and cfg:
        return [str(k).upper() for k in cfg.keys()]

    return []


def extract_token(label, project_prefixes):
    """Retire le préfixe projet pour obtenir le token métier"""
    label_upper = label.upper()
    for prefix in project_prefixes:
        if label_upper.startswith(prefix + "_"):
            return prefix, label_upper[len(prefix) + 1:]
    return None, label_upper


# ---------------------------------------------------
# Index récursif des QML
# ---------------------------------------------------
def index_qml_files(style_folder: str):
    """
    Parcourt récursivement style_folder et construit :
      - by_stem: dict { STEM_UPPER: [fullpath1, fullpath2, ...] }
      - all_items: liste de tuples (STEM_UPPER, fullpath)
    """
    by_stem = {}
    all_items = []

    for root, _, files in os.walk(style_folder):
        for fn in files:
            if not fn.lower().endswith(".qml"):
                continue
            stem = os.path.splitext(fn)[0].upper()
            full = os.path.join(root, fn)
            by_stem.setdefault(stem, []).append(full)
            all_items.append((stem, full))

    return by_stem, all_items


def choose_best(paths, prefer_under=None):
    """
    Choix déterministe si plusieurs fichiers matchent.
    - Si prefer_under est fourni, on préfère les fichiers sous ce sous-dossier
    - Ensuite : chemin le plus court, puis tri alpha
    """
    if not paths:
        return None

    if prefer_under:
        prefer_under = os.path.normpath(prefer_under).lower()
        preferred = [p for p in paths if os.path.normpath(p).lower().startswith(prefer_under)]
        if preferred:
            paths = preferred

    paths = sorted(paths, key=lambda p: (len(os.path.normpath(p)), os.path.normpath(p).lower()))
    return paths[0]


def strict_token_match(pattern_upper: str, stem_upper: str):
    """Match strict du token : délimiteurs '_' ou '-' ou début/fin"""
    pat = re.escape(pattern_upper)
    return re.search(rf"(^|[_\-]){pat}($|[_\-])", stem_upper) is not None


# ---------------------------------------------------
# Fonction principale : 100% récursive
# ---------------------------------------------------
def get_style(layer_path, style_folder):
    """
    Sélectionne le fichier de style (.qml) le plus approprié.
    Toutes les recherches sont récursives (dossier + sous-dossiers).

    Règle métier :
      - si couche préfixée par un projet (ex: SITUATION_...) :
          1) chercher style exact avec préfixe (SITUATION_X.qml) en récursif
          2) sinon enlever le préfixe => chercher style exact (X.qml) en récursif
      - sinon :
          1) chercher style exact (LABEL.qml) en récursif
      - puis fallback heuristiques en récursif :
          token+geom, puis token seul (strict)
    """
    if not style_folder:
        raise ValueError("Global 'styles_directory' is not set")
    if not os.path.isdir(style_folder):
        return None

    label, _path = next(iter(layer_path.items()))
    label_upper = label.upper()

    project_prefixes = get_project_prefixes()
    token_prefix, base_label = extract_token(label_upper, project_prefixes)

    # Index récursif (1 seul walk)
    by_stem, all_items = index_qml_files(style_folder)


    # Exemple : base_label = ASSEMBLAGE_VEGE_poly -> contexte "ASSEMBLAGE" 
    prefer_under = None
    #first_word = base_label.split("_")[0]
    #candidate_folder = os.path.join(style_folder, first_word)
    if token_prefix:
        project_folder = os.path.join(style_folder, token_prefix)
        if os.path.isdir(project_folder):
            prefer_under = project_folder

    # -----------------------------
    # 1) Cas préfixé projet : chercher exact préfixé
    # -----------------------------
    if token_prefix:
        prefixed_paths = by_stem.get(label_upper, [])
        hit = choose_best(prefixed_paths, prefer_under=prefer_under)
        if hit:
            print(f"Style trouvé (exact, récursif) avec préfixe projet '{token_prefix}': {hit}")
            return hit

        # -----------------------------
        # 2) Fallback : enlever SITUATION_ et chercher exact
        # -----------------------------
        unprefixed_paths = by_stem.get(base_label, [])
        hit = choose_best(unprefixed_paths, prefer_under=prefer_under)
        if hit:
            return hit

    else:
        # -----------------------------
        # Cas non préfixé : exact direct
        # -----------------------------
        exact_paths = by_stem.get(base_label, [])
        hit = choose_best(exact_paths, prefer_under=prefer_under)
        if hit:
            return hit

    # -----------------------------
    # Fallback heuristiques (toujours récursif)
    # -----------------------------
    parts = base_label.split("_")
    geom = None
    token = None

    if len(parts) >= 2 and parts[-1] in ("poly", "line", "point"):
        geom = parts[-1]
        token = "_".join(parts[:-1])
    elif len(parts) >= 2:
        token = parts[-1]
    else:
        token = base_label

    # A) token+geom exact
    if geom:
        target = f"{token}_{geom}".upper()
        paths = by_stem.get(target, [])
        hit = choose_best(paths, prefer_under=prefer_under)
        if hit:
            return hit

    # --- Fallback SAFE : token seul exact ---
    token_only = token.upper()
    paths = by_stem.get(token_only, [])
    hit = choose_best(paths, prefer_under=prefer_under)
    if hit:
        return hit

    # PAS DE fallback cross-token
    print(f"Aucun style métier trouvé pour {label_upper}")
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


# region PARCA_index


from pathlib import Path

def build_parca_index(folders_folder):
    """Fonction d’indexation pour recheche des dossier contenant une couche PARCA"""

    if not folders_folder:
        pass

    project_root = Path(folders_folder)

    index = []

    for file in project_root.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in [".gpkg", ".shp", ".geojson"]:
            continue

        filename = file.stem.lower()

        if "parca" in filename:

            layer_name = file.stem

            if "SEQ_PARCA_poly" in layer_name:
                project_name = layer_name.split("_SEQ")[0]
            elif "PARCA_polygon" in layer_name:
                project_name = layer_name.split("_PARCA")[0]
            else:
                continue

            index.append({
                "project_name": project_name,
                "folder": file.parent,
                "file": file
            })

    print(f"Index PARCA construit : {len(index)} couches trouvées")
    return index