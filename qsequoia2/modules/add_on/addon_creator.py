"""
/***************************************************************************
                                 QSEQUOIA2 ADD-ON
QSEQUOIA2 addon creator
                             -------------------

SequoiAPP(Qsequoia2)

/***************************************************************************
"""

# -*- coding: utf-8 -*-

# python
import re, shutil
from pathlib import Path

# QGIS
from PyQt5.QtWidgets import QDialog
from qgis.PyQt.QtWidgets import QInputDialog
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.core import *
from ..utils.Qmessage import *
from ..utils.plugin_vars import *

# endregion
# ==========================================================================
# addonCreator
# ==========================================================================
TEXT_EXT = {".py", ".ui", ".json", ".txt", ".md", ".yaml", ".yml"}

TEMPLATE_DIR = PLUGIN_DIR /"modules"/"add_on"/ "templates"/ "basic_addon" 

def on_new_addon_clicked(iface, addons_dir, plugin):

    try:
        addons_dir = Path(addons_dir)
        text, ok = QInputDialog.getText(
            iface.mainWindow(),
            "Création d'un Add-on",
            "Entrez un nom :"
        )

        if not ok or not text.strip():
            addon_name = "my_qs2_addon"
        else:
            addon_name = text.strip().lower()

        addon_dir = copy_addon_template(addon_name, addons_dir)

        addon_class = create_addon_class(addon_name)

        process_addon(addon_dir, addon_name, addon_class)

        messageBar(iface, f"Add-on créé : {addon_name}","s",5)

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(addon_dir)))

    except Exception as e:
        messageBar(iface, f"Échec de la création {str(e)}", "w",10)
        

def copy_addon_template(addon_name, addons_dir):
    """
    Crée physiquement le nouvel add-on à partir du modèle de base.
    :return: Chemin absolu du dossier de l’add-on créé.
    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", addon_name):
        raise Exception("Nom invalide (lettres, chiffres et _ uniquement)")

    # nom du dossier et de la classe
    addon_folder_name = f"{addon_name}"
    addon_dir = Path(addons_dir) / addon_folder_name
    if Path(addon_dir).is_dir():
        raise Exception(f"Addon {addon_name} déjà existant")

    shutil.copytree(TEMPLATE_DIR, addon_dir)
    return addon_dir


def create_addon_class(addon_name):
    return f"{"".join(word.capitalize() for word in addon_name.split("_"))}"

def process_addon(addon_dir: Path, addon_name: str, addon_class: str):
    # --- Remplacer les variables dans les fichiers texte ---
    for path in addon_dir.rglob("*"):
        if path.is_file() and path.suffix in TEXT_EXT:
            content = path.read_text(encoding="utf-8")
            content = content.replace("{{ADDON_NAME}}", addon_name)
            content = content.replace("{{ADDON_CLASS}}", addon_class)
            path.write_text(content, encoding="utf-8")

    # --- Renommer les fichiers template ---
    for path in addon_dir.rglob("*"):
        if path.is_file():
            # Renommer les fichiers commençant par template_addon
            if path.name.startswith("template_addon"):
                new_name = path.name.replace("template_addon", addon_name)
                path.rename(path.with_name(new_name))

            # Supprimer certains fichiers
            if path.name in {"addons.ui", "addon.py", "addon.ui", "_functions.yaml"}:
                path.unlink()

    return addon_dir