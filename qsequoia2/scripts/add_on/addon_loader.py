"""
/***************************************************************************
                                 QSEQUOIA2 ADD-ON
QSEQUOIA2 addon loader
                             -------------------

 Alexandre Le Bars - comité des forêts 2026  - SequoiAPP(Qsequoia2)
"""

# -*- coding: utf-8 -*-
# ==========================================================================
# region import
# ==========================================================================

# python
import os
import importlib.util

#QGIS
from PyQt5.QtGui import QIcon
from qgis.core import *

# Qsequoia2
from ..utils.variable import get_global_variable
from ..utils.messageBar import *

# endregion
# ==========================================================================
# region load_addons
# ==========================================================================

def load_addons(plugin, iface):
    """
    Charge et initialise tous les add-ons QS2 présents dans le dossier dédié.

    Pour chaque sous-dossier du dossier des add-ons :
    - le script Python correspondant est importé dynamiquement,
    - la classe principale de l'add-on est instanciée avec les paramètres du plugin,
    - l'onglet fourni par l'add-on est ajouté au QTabWidget du plugin,
    - une icône est chargée si disponible.

    Les add-ons chargés sont également stockés dans `plugin.addons_tabs` pour
    un accès ultérieur.

    :param plugin: Instance principale du plugin QSequoia2.
    :type plugin: object

    :param current_project_name: Nom du projet actif.
    :type current_project_name: str

    :param current_style_folder: Chemin vers le dossier des styles QGIS.
    :type current_style_folder: str

    :param downloads_path: Chemin vers le dossier de téléchargements.
    :type downloads_path: str

    :param current_project_folder: Dossier racine du projet courant.
    :type current_project_folder: str

    :param iface: Interface QGIS pour accéder aux fonctionnalités du GUI.
    :type iface: QgisInterface

    :return: Liste des instances des add-ons chargés.
    :rtype: list
    """

    addons_path = get_global_variable("QS2_addon_folder")

    loaded_addons = []

    for folder in os.listdir(addons_path):
        addon_dir = os.path.join(addons_path, folder)
        folder_name = os.path.basename(addon_dir)
        addon_name = folder_name.split("_QS2Addon")[0]
        addon_file = os.path.join(addon_dir, f"{addon_name}_QS2Addon.py")
        if not os.path.exists(addon_file):
            messageBar(iface, f"Erreur de chargement : {addon_file} not found","w", 10)
            continue

        try:
            spec = importlib.util.spec_from_file_location(folder, addon_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            class_name = f"{addon_name}_QS2Addon"
            addon_class = getattr(module, class_name)

            addon = addon_class(plugin=plugin,iface=iface)

            loaded_addons.append(addon)

            # --- Récupération du tab et ajout au QTabWidget ---
            tab = addon.get_tab()
            name = addon.get_name()
            icon_path = os.path.join(addon_dir, "icon.svg")
            icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

            index = plugin.tabWidget.addTab(tab, icon, "")
            plugin.tabWidget.setTabToolTip(index, name)

            messageLog("Your addon has been correctly loaded","i")

        except Exception as e:
            messageBar(iface, f"[QSEQUOIA addon] Erreur de chargement {str(e)}","w",10)

    # Stocker dans le dockwidget pour propagation future
    plugin.addons_tabs = loaded_addons

    return loaded_addons
# endregion