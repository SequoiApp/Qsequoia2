import os
import shutil
from qgis.core import QgsApplication
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog
from qgis.core import Qgis

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'addon.ui'))


class addonCreator(QDialog ,FORM_CLASS):
    def __init__(self, iface, addon_folder,plugin, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plugin = plugin
        self.addon_folder = addon_folder
        self.iface = iface
        self.script_dir = os.path.dirname(__file__)
        self.new_addon.clicked.connect(self.on_new_addon_clicked)


    def on_new_addon_clicked(self):

        try:
            addon_dir = self.create_addon()
            self.iface.messageBar().pushMessage("Qsequoia2",f"Add-on créé : {addon_dir}",level=Qgis.Success,duration=5)
            os.startfile(addon_dir)
            self.accept()
        except Exception as e:
            self.iface.messageBar().pushMessage("Erreur",str(e),level=Qgis.Critical,duration=5)

    def create_addon(self):

        if not self.addon_folder:
            raise Exception("Dossier d'addons non défini")

        template_path = os.path.join(self.script_dir, "templates", "basic_addon")

        addon_name = self.addon_name.text().strip()

        if not addon_name:
            self.labelErreur.setText("Nom obligatoire")
            self.labelErreur.setStyleSheet("color:red")
            raise Exception("Nom d'addon manquant")

        addon_dir = os.path.join(self.addon_folder, f"{addon_name}_QS2Addon")

        if os.path.exists(addon_dir):
            raise Exception(f"Addon {addon_name} déjà existant")

        shutil.copytree(template_path, addon_dir)
        
        def to_class_name(name):
            return "".join(word.capitalize() for word in name.split("_"))

        addon_class = to_class_name(addon_name)

        for root, dirs, files in os.walk(addon_dir):

            for file in files:

                path = os.path.join(root, file)

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                content = content.replace("{{ADDON_NAME}}", f"{addon_name}_QS2Addon")
                content = content.replace("{{ADDON_CLASS}}", f"{addon_class}_QS2Addon")

                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

                # renommer le fichier template
                if "addon" in file:

                    old_path = os.path.join(root, file)
                    new_file = file.replace("addon", f"{addon_name}_QS2Addon")
                    new_path = os.path.join(root, new_file)

                    os.rename(old_path, new_path)

        return addon_dir