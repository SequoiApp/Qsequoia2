"""
/***************************************************************************
                                 QSEQUOIA2 ADD-ON
QSEQUOIA2 addon creator
                             -------------------

 Alexandre Le Bars - comité des forêts 2026  - SequoiAPP(Qsequoia2)
"""

# -*- coding: utf-8 -*-
# ==========================================================================
# region import
# ==========================================================================

# python
import os, re, shutil
from pathlib import Path

# QGIS
from qgis.core import QgsApplication
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog
from qgis.PyQt.QtWidgets import QInputDialog
from qgis.core import Qgis

# endregion
# ==========================================================================
# region addonCreator
# ==========================================================================

class addonCreator(QDialog):

    def __init__(self, iface, addon_folder, plugin, parent=None):
        """
        Initialise le dialogue de création d’un add-on QSequoia2.

        Cette fenêtre permet de créer un nouvel add-on à partir d’un modèle
        (préfabriqué dans le dossier `templates/basic_addon`), en renseignant
        un nom valide. L’add-on sera créé dans le dossier spécifié.

        :param iface: Interface QGIS pour interagir avec l’interface utilisateur.
        :type iface: QgisInterface

        :param addon_folder: Dossier racine où seront créés les add-ons.
        :type addon_folder: str

        :param plugin: Instance du plugin QSequoia2 appelant.
        :type plugin: object

        :param parent: Widget parent Qt (optionnel).
        :type parent: QWidget | None
        """
        super().__init__(parent)

        self.plugin = plugin
        self.addon_folder = addon_folder
        self.iface = iface
        self.script_dir = os.path.dirname(__file__)


    def on_new_addon_clicked(self):
        """
        Déclenche la création d’un nouvel add-on lorsqu’un utilisateur clique sur le bouton.

        Étapes :
        1. Demande le nom de l’add-on via un QInputDialog.
        2. Vérifie la validité du nom (non vide, caractères valides).
        3. Crée le dossier et les fichiers de l’add-on via ``create_addon``.
        4. Affiche un message de succès dans la barre de QGIS.
        5. Ouvre le dossier nouvellement créé dans l’explorateur de fichiers.

        En cas d’erreur, un message critique est affiché et le dialogue est rejeté.

        :return: None
        """
        try:
            # Input dialog
            text, ok = QInputDialog.getText(self, "Nouvelle Add-on", "Entrez un nom :")

            if not ok or not text.strip():
                self.reject()
                return
            self.addon_name = text.capitalize()

            # Création de l'addon
            addon_dir = self.create_addon()

            # message QGIS
            self.iface.messageBar().pushMessage("QSequoia2",f"Add-on créé : {addon_dir}",level=Qgis.Success,duration=5)

            # ouvrir le dossier correctement
            os.startfile(str(Path(addon_dir).resolve()))

            self.accept()

        except Exception as e:
            self.iface.messageBar().pushMessage("Erreur",str(e),level=Qgis.Critical,duration=5)
            
            self.reject()


    def create_addon(self):
        """
        Crée physiquement le nouvel add-on à partir du modèle de base.

        Fonctionnalités :
        - Vérifie que le dossier de destination existe.
        - Vérifie que le nom d’add-on est défini et respecte la syntaxe Python.
        - Copie le template d’add-on dans un nouveau dossier.
        - Remplace les placeholders `{{ADDON_NAME}}` et `{{ADDON_CLASS}}` dans tous les fichiers texte.
        - Renomme les fichiers template pour correspondre au nom de l’add-on.
        - Retourne le chemin complet du nouvel add-on créé.

        :raises Exception: Si le dossier d’add-ons n’est pas défini.
        :raises Exception: Si le nom d’add-on est manquant ou invalide.
        :raises Exception: Si l’add-on existe déjà dans le dossier.

        :return: Chemin absolu du dossier de l’add-on créé.
        :rtype: str
        """

        if not self.addon_folder:
            raise Exception("Dossier d'addons non défini")

        template_path = os.path.join(self.script_dir, "templates", "basic_addon")

        if not self.addon_name:
            self.labelErreur.setText("Nom obligatoire")
            self.labelErreur.setStyleSheet("color:red")
            raise Exception("Nom d'addon manquant")

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", self.addon_name):
            self.labelErreur.setText("Nom invalide (lettres, chiffres et _ uniquement)")
            self.labelErreur.setStyleSheet("color:red")
            raise Exception("Nom invalide (lettres, chiffres et _ uniquement)")

        # nom du dossier et de la classe
        addon_folder_name = f"{self.addon_name}_QS2Addon"
        addon_dir = os.path.join(self.addon_folder, addon_folder_name)

        if os.path.exists(addon_dir):
            raise Exception(f"Addon {self.addon_name} déjà existant")

        shutil.copytree(template_path, addon_dir)

        def to_class_name(name):
            return "".join(word.capitalize() for word in name.split("_"))

        addon_class = f"{to_class_name(self.addon_name)}_QS2Addon"

        # remplacer les variables dans les fichiers texte
        for root, dirs, files in os.walk(addon_dir):
            for file in files:
                path = os.path.join(root, file)
                if file.endswith((".py", ".ui", ".json", ".txt", ".md")):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    content = content.replace("{{ADDON_NAME}}", addon_folder_name)
                    content = content.replace("{{ADDON_CLASS}}", addon_class)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)

        # renommer les fichiers template
        for root, dirs, files in os.walk(addon_dir):
            for file in files:
                if file.startswith("template_addon"):
                    old_path = os.path.join(root, file)
                    new_file = file.replace("template_addon", addon_folder_name)
                    new_path = os.path.join(root, new_file)
                    os.rename(old_path, new_path)
                    
                if file in ("addons.ui", "addon.py", "addon.ui"):
                    file_path = os.path.join(root, file)
                    os.remove(file_path)


        return addon_dir