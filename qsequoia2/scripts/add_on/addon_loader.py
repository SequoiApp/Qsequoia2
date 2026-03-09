import os
import importlib.util
from qgis.core import QgsApplication
from PyQt5.QtGui import QIcon


def get_addons_path():

    path = os.path.join(QgsApplication.qgisSettingsDirPath(),"QSEQUOIA2","addons")

    os.makedirs(path, exist_ok=True)

    return path

def load_addons(plugin):
    addons_path = get_addons_path()


    for folder in os.listdir(addons_path):
        addon_dir = os.path.join(addons_path, folder)
        addon_file = os.path.join(addon_dir, "addon.py")
        if not os.path.exists(addon_file):
            continue

        try:
            spec = importlib.util.spec_from_file_location(folder, addon_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            addon_class = module.QSequoiaAddon
            addon = addon_class(
                iface=plugin.iface,
                project_name=plugin.project_name,
                style_folder=plugin.current_style_folder,
                downloads_path=plugin.downloads_path,
                project_folder=plugin.current_project_folder
            )

            # --- Récupération du tab et ajout au QTabWidget ---
            tab = addon.get_tab()
            name = addon.get_name()
            icon_path = getattr(addon, "icon_path", None)
            icon = QIcon(icon_path) if icon_path else QIcon()

            index = plugin.tabWidget.addTab(tab, icon, "")
            plugin.tabWidget.setTabToolTip(index, name)

        except Exception as e:
            print(f"[QSEQUOIA addon] Erreur dans {folder} : {e}")