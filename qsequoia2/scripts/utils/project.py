""""""
import os
from qgis.core import *
from .messageBar import *

from qgis.PyQt.QtWidgets import QFileDialog, QInputDialog




#fonction set_projectFolder

def set_projectFolder(self, path=None):
    """
    Définit le dossier de projet actif.

    Cette fonction permet :
    - de sélectionner manuellement un dossier de projet si aucun chemin n'est fourni,
    - de déterminer automatiquement le nom du projet à partir des fichiers ou du nom du dossier,
    - de mettre à jour les variables internes du plugin (nom et chemin du projet),
    - de propager ces informations aux différents onglets du DockWidget,
    - de redémarrer les mécanismes de surveillance (watchdog),
    - de charger ou créer un projet QGIS (.qgz) si nécessaire,
    - de vérifier la présence de données forestières (PARCA) et lancer les calculs associés si disponibles.
    """

    #Selection des dossiers manuellement 

    if path is None :  #passe dans le cas ou un dossier de projet est créée
        path = QFileDialog.getExistingDirectory(self.dockwidget, "Select project Directory")

        if not path:
            self.current_project_folder = None
            self.current_project_name = None
            return

    messageLog(f"Selected directory: {path}","i")
    self.current_project_folder = path
    #SI chemin, on masque les suggestion de projet
    if path:

        self.suggestion_list.clear()
        self.suggestion_list.setVisible(False)
        self.suggestion_scroll.setVisible(False)
    #on grise le boutton add_project
    self.dockwidget.add_project.setEnabled(False)


    #extraction du nom du projet

    project_name = None

    #test pour trouver le nom d eprojet depuis des fichiers
    for root, dirs, files in os.walk(self.current_project_folder):
        for filename in files:

            if "_matrice" in filename:
                project_name = filename.split("_matrice")[0]
                break

            if "_SEQ_PARCA_poly" in filename:
                project_name = filename.split("_SEQ_PARCA_poly")[0]
                break

            if "_SEQ_PROJECT" in filename:
                project_name = filename.split("_SEQ_PROJECT")[0]

        if project_name:
            break

    #fallback sur le dossier de projet si rien trouvé
    if not project_name:
        folder_name = os.path.basename(self.current_project_folder)
        if "_SIG" in folder_name:
            project_name = folder_name.split("_SIG")[0]
        if "_SEQ" in folder_name:
            project_name = folder_name.split("_SEQ")[0]
        if "SEQ_SIG" in folder_name:
            project_name = folder_name.split("_SEQ_SIG")[0]

        #Pour les anciennes couches et anciens projets
        if folder_name == "SIG":
            for nom in os.listdir(self.current_project_folder):
                if "SEQ_PARCA_poly" in nom:
                    continue
                if "PARCA" in nom:
                    project_name = nom.split("_PARCA")[0]
                    break

    if not project_name:
        project_name, ok = QInputDialog.getText(None,"Nom du projet", "Impossible de déterminer le nom du projet.\nVeuillez saisir le nom du projet :")

        if not ok or not project_name.strip():
            self.current_project_folder = None
            raise Exception("Nom du projet non fourni. Opération annulée.")

    self.current_project_name = project_name

    #--- Propagation au DockWidget ---
    if self.dockwidget:
        self.dockwidget.current_project_name = self.current_project_name
        self.dockwidget.current_project_folder = self.current_project_folder

        #Afficher uniquement le nom du projet dans le champ
        self.dockwidget.cb_seq_folder.blockSignals(True)
        self.dockwidget.cb_seq_folder.setText(self.current_project_name)
        self.dockwidget.cb_seq_folder.blockSignals(False)
        self.dockwidget.cb_seq_folder.setEnabled(False)

        #Propager aux onglets
        if hasattr(self.dockwidget, "tools_tab"):
            self.dockwidget.tools_tab.current_project_name = self.current_project_name
            self.dockwidget.tools_tab.current_project_folder = self.current_project_folder

        if hasattr(self.dockwidget, "data_settings_tab"):
            self.dockwidget.data_settings_tab.current_project_name = self.current_project_name
            self.dockwidget.data_settings_tab.current_project_folder = self.current_project_folder
    
        if hasattr(self.dockwidget, "LayoutDesigner_tab"):
            self.dockwidget.LayoutDesigner_tab.current_project_name = self.current_project_name
            self.dockwidget.LayoutDesigner_tab.current_project_folder = self.current_project_folder
    
        if hasattr(self.dockwidget, "forest_data_tab"):
            self.dockwidget.forest_data_tab.current_project_name = self.current_project_name
            self.dockwidget.forest_data_tab.current_project_folder = self.current_project_folder
    
        #--- Propagation aux addons chargés ---
        if hasattr(self.dockwidget, "addons_tabs"):
            for addon in self.dockwidget.addons_tabs:
                addon.current_project_name = self.current_project_name
                addon.current_project_folder = self.current_project_folder


    #Mise à jour éventuelle du connect_dialog
    if self.connect_dialog:
        self.connect_dialog.update_watch_path_label()

    #redémarrer le watcher
    if self.dogwatcher:
        self.dogwatcher.restart()

        messageLog(f"Project name => {self.current_project_name}", "i")

    # Vérifier si dossier contient un projet QGZ, si non, on le crée, uniquement si variable utilisateur

    project = QgsProject.instance()

    if self.QSS2_default_project == "true" or True :
        project_path = ensure_and_load_qgis_project(
            project,
            project_folder=self.current_project_folder,
            project_name=self.current_project_name,
            epsg="EPSG:2154")
    
        messageLog(f"Projet QGZ chargé : {project_path}", "i")

    messageBar(self.iface, f"Dossier {self.current_project_name} sélectionné avec succès : {self.current_project_folder}","s",10)

    #Vérifier s'il y a une couche PARCA dans le dossier projet

    parca_files = any("PARCA" in name.upper()for root, dirs, files in os.walk(self.current_project_folder)for name in dirs + files)

    #Si une couche Parca existe, on lance le calcul des metadonnées de bases

    if not parca_files:
        messageLog("Aucune couche PARCA trouvée dans le dossier du projet. Calcul forestier annulé.","w")
    else:
        try:
            forest_data = getForestdata(
                project_name=project_name,
                project_folder=self.current_project_folder,
                style_folder=self.current_style_folder,
                iface=self.iface)
        
            forest_data.run_all_calculations()
        except Exception as e:
            messageLog(f"Erreur lors du calcul des metadata : {e}","w")

on_project_name_changed

def on_project_name_changed(self, text):
    """
    Gère les modifications du nom de projet saisies par l'utilisateur.

    Cette fonction :
    - met à jour le nom du projet courant,
    - propose automatiquement des dossiers de projet existants correspondant au texte saisi,
    - affiche une liste de suggestions si des correspondances sont trouvées,
    - active ou désactive le bouton de création de projet selon la validité du texte,
    - propage le nom du projet aux composants du DockWidget,
    - redémarre le système de surveillance si nécessaire.
    """

    #si le changement vient du code → on ignore
    if self.updating_project_name:
        return

    self.current_project_name = text

    #Activation du bouton
    text_clean = text.strip()
    text_valid = bool(text_clean)   #vrai uniquement si texte non vide

    #Propager au DockWidget
    if self.dockwidget:
        self.dockwidget.current_project_name = self.current_project_name
        self.dockwidget.cb_seq_folder.blockSignals(True)
        self.dockwidget.cb_seq_folder.setText(self.current_project_name)
        self.dockwidget.cb_seq_folder.blockSignals(False)

    #   Propager aux onglets si nécessaire
        if hasattr(self.dockwidget, "tools_tab"):
            self.dockwidget.tools_tab.current_project_name = self.current_project_name
    
        if hasattr(self.dockwidget, "data_settings_tab"):
            self.dockwidget.data_settings_tab.current_project_name = self.current_project_name


    if text:   #éviter de lancer sur vide
        if self.dogwatcher:
            self.dogwatcher.restart()

        else:
            messageLog("Watcher non initialisé, rien à redémarrer.","w")

add_project_clicked
def add_project_clicked(self):
    """
    Crée un nouveau dossier de projet à partir du nom saisi par l'utilisateur.

    Si la création du dossier réussit :
    - le dossier est défini comme dossier de projet actif,
    - le processus de chargement du projet est lancé.

    Si la création est annulée ou échoue, aucune modification n'est appliquée.
    """

    folder_path = create_new_folder(
        project_name=self.current_project_name,
        parent_widget=self.dockwidget,
        log=None,
        dockwidget=self.dockwidget,
        iface=self.iface)

    if folder_path and os.path.isdir(folder_path):
        self.set_projectFolder(folder_path)

get_watchdog_context