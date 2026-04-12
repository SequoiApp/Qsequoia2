"""Script de création d'un fichier yaml contenant l'ensemble des fonctions, classe et méthodes de Qsequoia2"""


import ast
import yaml
from pathlib import Path
from typing import List, Dict, Any

# --------------------------------------------------------------------------
# Dossier racine du plugin QSequoia2
# --------------------------------------------------------------------------
ROOT: Path = Path(__file__).parent /".."/ "qsequoia2"

# --------------------------------------------------------------------------
# Fonction utilitaire : récupération des arguments d'une fonction/méthode
# --------------------------------------------------------------------------
def get_args(node: ast.AST) -> List[str]:
    """
    Extrait la liste des arguments nommés d'une fonction ou d'une méthode.

    Args:
        node (ast.AST): Node AST représentant une fonction (ast.FunctionDef) 
                        ou une méthode.

    Returns:
        List[str]: Liste des noms d'arguments dans l'ordre.
    
    Notes:
        - Ne récupère pas *args, **kwargs ni les annotations.
        - Retourne une liste vide si aucun argument.
    """
    args: List[str] = []

    if hasattr(node, "args"):
        for a in node.args.args:
            args.append(a.arg)

    return args

# --------------------------------------------------------------------------
# Fonction principale : scanner un fichier Python
# --------------------------------------------------------------------------
def scan_file(file_path: Path) -> Dict[str, Any]:
    """
    Analyse un fichier Python et extrait toutes les fonctions et classes définies.

    Args:
        file_path (Path): Chemin vers le fichier .py à scanner.

    Returns:
        Dict[str, Any]: Dictionnaire contenant les fonctions et classes du fichier.
            - Clé : nom de la fonction ou classe
            - Valeur : dictionnaire contenant :
                - type : "function" ou "class"
                - path : chemin du module sous forme de package Python
                - name : nom de la fonction ou classe
                - args : liste des arguments pour les fonctions (si applicable)
    
    Notes:
        - Les fichiers templates ou invalides sont ignorés automatiquement.
        - Les noms de modules sont convertis pour correspondre à l'import Python.
    """
    entries: Dict[str, Any] = {}

    try:
        source: str = file_path.read_text(encoding="utf-8")
        tree: ast.Module = ast.parse(source)
    except SyntaxError:
        # Ignorer les fichiers contenant du code incomplet ou des placeholders
        print("Skipped template:", file_path)
        return entries

    module_path: str = file_path.relative_to(ROOT.parent).with_suffix("").as_posix().replace("/", ".")

    for node in tree.body:

        if isinstance(node, ast.FunctionDef):
            # Entrée pour une fonction
            entries[node.name] = {
                "type": "function",
                "path": module_path,
                "name": node.name,
                "args": get_args(node)
            }

        elif isinstance(node, ast.ClassDef):
            # Entrée pour une classe
            entries[node.name] = {
                "type": "class",
                "path": module_path,
                "name": node.name
            }

    return entries

# --------------------------------------------------------------------------
# Fonction secondaire : scanner tout le package
# --------------------------------------------------------------------------
def scan_package(root: Path, ignore_dirs: list = None) -> dict:
    """
    Parcourt récursivement tous les fichiers Python d'un package et construit
    un registre complet des fonctions et classes.

    Args:
        root (Path): Dossier racine à scanner.

    Returns:
        Dict[str, Any]: Dictionnaire global de toutes les fonctions et classes
                        du package.
    
    Notes:
        - Ignore tous les fichiers __init__.py et templates.
        - Combine tous les résultats de scan_file.
    """
    ignore_dirs = ignore_dirs or []
    registry = {}

    for file in root.rglob("*.py"):
        if file.name.startswith("__"):
            continue
        if is_ignored(file, ignore_dirs):
            continue
        registry.update(scan_file(file))
    return registry
# --------------------------------------------------------------------------
# fichiers ignorer 
# --------------------------------------------------------------------------
def is_ignored(file: Path, ignore_dirs: list) -> bool:
    """
    Vérifie si un fichier doit être ignoré selon la liste de dossiers.
    Chaque élément de ignore_dirs peut être un chemin relatif avec plusieurs sous-dossiers.
    """
    for ignored in ignore_dirs:
        ignored_parts = Path(ignored).parts
        # Vérifie si ignored_parts apparaît consécutivement dans file.parts
        for i in range(len(file.parts) - len(ignored_parts) + 1):
            if file.parts[i:i+len(ignored_parts)] == ignored_parts:
                return True
    return False

# --------------------------------------------------------------------------
# Exécution : génération du YAML
# --------------------------------------------------------------------------
registry = scan_package(ROOT, ignore_dirs=["config/lib"]) #Dossier à ignorer

yaml_: Path = Path(__file__).parent /".."/ "qsequoia2"/"config"/"QS2_functions_registry.yaml"

with open(yaml_, "w", encoding="utf-8") as f:
    # Ajouter un commentaire d’avertissement en tête
    f.write("# Ce fichier est généré automatiquement par func_doc. Ne pas modifier manuellement.\n\n")
    yaml.dump(registry, f, allow_unicode=True, sort_keys=False)

print("YAML généré avec annotation de non-modification.")