"""
/***************************************************************************
                                 QSEQUOIA2 ADD-ON
QSEQUOIA2 addon loader
                             -------------------

SequoiAPP(Qsequoia2)

/***************************************************************************
"""
# -*- coding: utf-8 -*-

# python
from pathlib import Path
import importlib.util
import re
import sys
#QGIS
from PyQt5.QtGui import QIcon
from qgis.core import *

# Qsequoia2
from ..utils.variable import get_global_variable
from ..utils.Qmessage import *

# ==========================================================================
# load_addons
# ==========================================================================

def load_addons(plugin, iface):
    """
    Charge et initialise tous les add-ons QS2 présents dans le dossier dédié.

    Les add-ons chargés sont également stockés dans `plugin.addons_tabs` pour
    un accès ultérieur.

    :param plugin: Instance principale du plugin QSequoia2.
    :type plugin: object

    :param iface: Interface QGIS pour accéder aux fonctionnalités du GUI.
    :type iface: QgisInterface

    :return: Liste des instances des add-ons chargés.
    """

    addons_dir = Path(get_global_variable("QS2_addon_folder"))


    loaded_addons = []

    sys.path.insert(0, str(addons_dir))  # Ajout du dossier d'addons au path pour les imports

    # Parcours des dossiers d'addons
    for folder in addons_dir.iterdir():
        if not folder.is_dir():
            continue

        addon_dirname = folder.name
        addon_main_file = folder / "__init__.py"
        addon_id = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", addon_main_file.read_text(encoding="utf-8"))
        addon_id = addon_id.group(1) if addon_id else None

        if not addon_main_file.exists():
            messageBar(iface, f"Erreur de chargement : {addon_main_file} not found", "w", 10)
            continue

        # try:
        # --- Import dynamique du module ---
        spec = importlib.util.spec_from_file_location(f"{addon_dirname}", addon_main_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # --- Instanciation de la classe ---
        class_name = f"{addon_id}"
        addon_class = getattr(module, class_name)

        addon = addon_class(plugin=plugin, iface=iface)
        loaded_addons.append(addon)

        # --- Récupération du tab ---
        tab = addon.get_tab()
        name = addon.get_name()

        icon_path = folder / "icon.svg"
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()

        index = plugin.tabWidget.addTab(tab, icon, "")
        plugin.tabWidget.setTabToolTip(index, name)

        messageLog("Your addon has been correctly loaded", "i")

        # except Exception as e:
        #     messageBar(iface, f"[QSEQUOIA addon] Erreur de chargement {str(e)}", "w", 10)
        #     messageLog(f"[QSEQUOIA addon] Failed to load addon {addon_dirname}: {str(e)}", "w")

    # Stockage pour propagation future
    plugin.addons_tabs = loaded_addons

    return loaded_addons
