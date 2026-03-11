"""Ce module reprend des fonctions qui renvoie l'utilisateur sur les pages web correspondantes"""


import webbrowser, os, yaml
from qgis.gui import QgsMessageBar
from ...utils.messageBar import *

def go_to_net(action, iface, dockwidget=None):
    """
    Ouvre un outil web en récupérant son URL dans le YAML des URLs
    """
    if not action:
        return

    category = action.get("category")
    key = action.get("key")

    if not category or not key:
        return

    # Chemin vers le YAML des URLs
    plugin_dir = os.path.dirname(__file__)
    yaml_path = os.path.join(plugin_dir, "..", "..", "..", "inst", "qseq_URLS.yaml")

    with open(yaml_path, "r", encoding="utf-8") as f:
        urls_config = yaml.safe_load(f)

    # Récupération de l'entrée dans le YAML
    item_data = urls_config.get(category, {}).get(key)
    if not item_data:
        messageBar(iface, f"Impossible d'ouvrir {display_name}!", "w", 10)
        return

    url = item_data.get("url")
    display_name = item_data.get("display_name", key)

    if url:
        messageLog(f"Go to NET => ouverture de {display_name} ({url})", "i")

        webbrowser.open(url)
    else:
        messageBar(iface, f"Impossible d'ouvrir {display_name}!","w",10)








