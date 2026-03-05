import importlib
import console
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QComboBox, QVBoxLayout, QFrame, QPushButton
from qgis.core import QgsApplication, Qgis
from qgis.PyQt.QtWidgets import QMessageBox,QFileDialog, QInputDialog, QListWidget, QScrollArea
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QTimer, QThread, QMetaObject, Qt, pyqtSlot
from qgis.core import QgsProject, QgsCoordinateReferenceSystem


import yaml, timer

from qsequoia2.scripts.global_settings.global_settings import GlobalSettingsDialog
from qsequoia2.scripts.utils.variable import get_global_variable, set_global_variable
from qsequoia2.scripts.watchdog.dogwatcher import DogWatcher
from .scripts.utils.new_project import *
from .scripts.utils.suggest_project_folder import *
from.scripts.utils.config import *
from .scripts.forest_settings.forest_get_data import getForestdata
from .scripts.project_settings.project_settings import ProjectSettingsDialog
from .scripts.utils.reloader import reloadQS2



from .resources import *

# Import the code for the DockWidget
from .QSEQUOIA2_dockwidget import QSEQUOIA2DockWidget
import os.path


from .scripts.tools_settings.PY.unload import unknown_data

from .scripts.utils.connect_label import connect_label

from .scripts.utils.get_download_folder import get_download_folder

from .scripts.utils.extract_files import show_add_banner

from .scripts.utils.add_seq_config import add_seq_config

import sys

plugin_path = os.path.dirname(__file__)
watchdog_path = os.path.join(plugin_path, "inst", "lib")

if watchdog_path not in sys.path:
    sys.path.insert(0, watchdog_path)

from watchdog.observers import Observer

from .scripts.utils.watchdog_handler import DownloadEventHandler



class QSEQUOIA2:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)


        # initialize locale
        locale_value = QSettings().value('locale/userLocale', 'en')
        locale = str(locale_value)[:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            f'QSEQUOIA2_{locale}.qm'
        )


        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&QSEQUOIA2')

        # Trouver le chemins du dossier de téléchargement
        self.updating_project_name = False

        # Watchdog
        self.watch_mode = "auto"
        # valeurs possibles : "auto", "downloads", "project"



        self.current_project_name = None

        print(" \nDownoload the last version of Rsequoia2 config files…")
        add_seq_config()

        self.user_name = get_global_variable("user_full_name") or "Utilisateur QSEQUOIA2"
        print(" \nWelcome ! ", self.user_name)

        self.current_style_folder = get_global_variable("styles_directory") or None
        print(" \n==> Style folder at init:", self.current_style_folder)
        self.current_project_folder = None


        # Création du watchdog
        self.downloads_path = get_download_folder()
        print("Téléchargements :", self.downloads_path)
        self.connect_dialog = None

        self.dogwatcher = DogWatcher(iface=self.iface, get_context_callback=self.get_watchdog_context, parent=None)


        # Connaitre l'état des paramètres QS2

        self.QSS2_default_project = get_global_variable("QS2_default_project")

        self.folders_folder = get_global_variable("folders_folder") or None

        raw = get_global_variable("QS2_suggest_project")

        if raw is None:
            # valeur par défaut
            self.QS2_suggest_project = False
            set_global_variable("QS2_suggest_project", False)
        else:
            # normalisation
            if isinstance(raw, str):
                self.QS2_suggest_project = raw.strip().lower() == "true"
            else:
                self.QS2_suggest_project = bool(raw)
        
        self.parca_index = build_parca_index(self.folders_folder)


        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'QSEQUOIA2')
        self.toolbar.setObjectName(u'QSEQUOIA2')

        #print "** INITIALIZING KARTENN_VPC"

        self.pluginIsActive = False
        self.dockwidget = None
        self.dlg = None



    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('QSEQUOIA2', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):


        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/QSEQUOIA2/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u''),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING QSEQUOIA2"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD QSEQUOIA2"

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&QSEQUOIA-2'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING KARTENN_VPC"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = QSEQUOIA2DockWidget(current_project_folder= self.current_project_folder, current_project_name=self.current_project_name, 
                                                      downloads_path = self.downloads_path, current_style_folder = self.current_style_folder, iface=self.iface)


            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # icon du main
            icon_path = os.path.join(plugin_path, "icon.png")
             
            pixmap = QPixmap(icon_path)

            self.dockwidget.icon.setPixmap(pixmap)
            self.dockwidget.icon.setScaledContents(True)
            self.dockwidget.icon.setFixedSize(128, 128)

            # bouttons d'ajout de couches


            # nom du projet

            self.dockwidget.name.setPlaceholderText("Nom du projet")
            self.dockwidget.name.textChanged.connect(self.on_project_name_changed)



            #global settings button

            self.dockwidget.setstyle.clicked.connect(self.open_global_settings)
            self.dockwidget.setstyle.setIcon(QIcon(plugin_path + "/icons/global_settings.svg"))

            self.dockwidget.project_folder.clicked.connect(lambda: self.set_projectFolder())

            self.dockwidget.add_project.setEnabled(False)





            # gestionnaire de connexion

            self.dockwidget.watchdog.clicked.connect(self.open_connect_label)
            self.dockwidget.watchdog.setIcon(QIcon(plugin_path + "/icons/watchdog_settings.svg"))

            self.dockwidget.add_project.setIcon(QIcon(plugin_path + "/icons/add_data.svg"))

            self.dockwidget.add_project.clicked.connect(self.add_project_clicked)

            # --- Zone de suggestions dans groupBox_3 ---
            self.suggestion_list = QListWidget(self.dockwidget)
            self.suggestion_list.setVisible(False)
            self.suggestion_list.itemClicked.connect(self.on_suggestion_item_clicked)

            # ScrollArea
            self.suggestion_scroll = QScrollArea(self.dockwidget)
            self.suggestion_scroll.setWidgetResizable(True)
            self.suggestion_scroll.setVisible(False)
            self.suggestion_scroll.setWidget(self.suggestion_list)

            # Ajout dans groupBox_3
            self.dockwidget.project_suggest.layout().addWidget(self.suggestion_scroll)


            # securité si le nom de projet est grisé
            if not self.current_project_name :
                self.dockwidget.name.setEnabled(True)


            # Reload the plugin 

            self.dockwidget.reload.clicked.connect(lambda: reloadQS2(plugin=self.iface))


            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

    def non_implemented_yet(self):
        QMessageBox.information(
            self.dockwidget,
            "Non implémenté",
            "Cette fonctionnalité n'est pas encore implémentée."
        )


    def set_projectFolder(self, path=None):
        if path is None :
            path = QFileDialog.getExistingDirectory(self.dockwidget, "Select project Directory")

            if not path:
                print("No directory selected")
                self.current_project_folder = None
                self.current_project_name = None
                return

        print("Selected directory:", path)
        self.current_project_folder = path

        if path:

            self.suggestion_list.clear()
            self.suggestion_list.setVisible(False)
            self.suggestion_scroll.setVisible(False)

        self.dockwidget.add_project.setEnabled(False)


        # extraction du nom du projet

        project_name = None

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

        # fallback si rien trouvé
        if not project_name:
            folder_name = os.path.basename(self.current_project_folder)
            if "_SIG" in folder_name:
                project_name = folder_name.split("_SIG")[0]
            if "_SEQ" in folder_name:
                project_name = folder_name.split("_SEQ")[0]
            if "SEQ_SIG" in folder_name:
                project_name = folder_name.split("_SEQ_SIG")[0]

            # Pour les anciennes couches et anciens projets
            if folder_name == "SIG":
                for nom in os.listdir(self.current_project_folder):
                    if "SEQ_PARCA_poly" in nom:
                        continue
                    if "PARCA" in nom:
                        project_name = nom.split("_PARCA")[0]
                        break

        if not project_name:
            project_name, ok = QInputDialog.getText(
                None,
                "Nom du projet",
                "Impossible de déterminer le nom du projet.\nVeuillez saisir le nom du projet :")

            if not ok or not project_name.strip():
                self.current_project_folder = None
                raise Exception("Nom du projet non fourni. Opération annulée.")


                

        self.current_project_name = project_name

        # --- Propagation au DockWidget ---
        if self.dockwidget:
            self.dockwidget.current_project_name = self.current_project_name
            self.dockwidget.current_project_folder = self.current_project_folder

            # Afficher uniquement le nom du projet dans le champ
            self.dockwidget.name.blockSignals(True)
            self.dockwidget.name.setText(self.current_project_name)
            self.dockwidget.name.blockSignals(False)
            self.dockwidget.name.setEnabled(False)

            # Propager aux onglets
            if hasattr(self.dockwidget, "tools_tab"):
                self.dockwidget.tools_tab.current_project_name = self.current_project_name
                self.dockwidget.tools_tab.current_project_folder = self.current_project_folder

            if hasattr(self.dockwidget, "data_settings_tab"):
                self.dockwidget.data_settings_tab.current_project_name = self.current_project_name
                self.dockwidget.data_settings_tab.current_project_folder = self.current_project_folder
            
            if hasattr(self.dockwidget, "project_settings_tab"):
                self.dockwidget.project_settings_tab.current_project_name = self.current_project_name
                self.dockwidget.project_settings_tab.current_project_folder = self.current_project_folder

        # Mise à jour éventuelle du connect_dialog
        if self.connect_dialog:
            self.connect_dialog.update_watch_path_label()

        

        # redémarrer le watcher
        if self.dogwatcher:
            self.dogwatcher.restart()


            print(f"Project name => {self.current_project_name}")
        
        # Vérifier si dossier contient un projet QGZ, si non, on le crée, uniquement si variable utilisateur
        project = QgsProject.instance()

        if self.QSS2_default_project == "true" or True :
            project_path = ensure_and_load_qgis_project(
                project,
                project_folder=self.current_project_folder,
                project_name=self.current_project_name,
                epsg="EPSG:2154")
            

            print(f"Projet QGZ chargé : {project_path}")
        
        self.iface.messageBar().pushMessage(
            "Qsequoia2",
            f"Dossier {self.current_project_name} sélectionné avec succès : {self.current_project_folder}",
            level=Qgis.Success, duration=10)
        
        # Vérifier s'il y a une couche PARCA dans le dossier projet
        parca_files = any("PARCA" in name.upper()for root, dirs, files in os.walk(self.current_project_folder)for name in dirs + files)

        if not parca_files:
            print("Aucune couche PARCA trouvée dans le dossier du projet. Calcul forestier annulé.")
        else:
            try:
                forest_data = getForestdata(
                    project_name=project_name,
                    project_folder=self.current_project_folder,
                    style_folder=self.current_style_folder,
                    iface=self.iface
                )
                forest_data.run_all_calculations()
            except Exception as e:
                print(f"Erreur lors du calcul forestier : {e}")

    
    def on_project_name_changed(self, text):

        # si le changement vient du code → on ignore
        if self.updating_project_name:
            return

        self.current_project_name = text

        self.current_project_name = text

        # Proposition des dossier de projets
        if self.QS2_suggest_project:

            project_folders, project_names = suggest_project_folder(text, self.parca_index)


            # Nettoyage
            self.suggestion_list.clear()
            self.suggestion_list.setVisible(False)
            self.suggestion_scroll.setVisible(False)

            # Aucune suggestion
            if not project_names:
                return


            if len(text) == 0:
                self.suggestion_list.clear()
                self.suggestion_list.setVisible(False)
                self.suggestion_scroll.setVisible(False)

            # Affichage des suggestions uniquement si texte long ou suggestions existantes
            if project_names and len(text.strip()) >= 3:
                self.current_suggested_folders = project_folders
                for folder, name in zip(project_folders, project_names):
                    self.suggestion_list.addItem(f"{name} : {folder}")
                self.suggestion_scroll.setVisible(True)
                self.suggestion_list.setVisible(True)

        # Activation du bouton
        text_clean = text.strip()
        text_valid = bool(text_clean)  # vrai uniquement si texte non vide
        has_suggestions = self.QS2_suggest_project and bool(project_folders)

        # Si le texte est vide → bouton désactivé, même s'il y a des suggestions
        enable_add_project = text_valid or (text_valid and has_suggestions)

        self.dockwidget.add_project.setEnabled(enable_add_project)

        # Propager au DockWidget
        if self.dockwidget:
            self.dockwidget.current_project_name = self.current_project_name
            self.dockwidget.name.blockSignals(True)
            self.dockwidget.name.setText(self.current_project_name)
            self.dockwidget.name.blockSignals(False)

            # Propager aux onglets si nécessaire
            if hasattr(self.dockwidget, "tools_tab"):
                self.dockwidget.tools_tab.current_project_name = self.current_project_name
            
            if hasattr(self.dockwidget, "data_settings_tab"):
                self.dockwidget.data_settings_tab.current_project_name = self.current_project_name


        if text:  # éviter de lancer sur vide
            if self.dogwatcher:
                self.dogwatcher.restart()

            else:
                print("Watcher non initialisé, rien à redémarrer.")

    def on_suggestion_item_clicked(self, item):

        selected_name = item.text()
        index = self.suggestion_list.row(item)
        selected_folder = self.current_suggested_folders[index]

        # Mise à jour du QLineEdit
        self.dockwidget.name.blockSignals(True)
        self.dockwidget.name.setText(selected_name)
        self.dockwidget.name.blockSignals(False)

        # Cacher la zone de suggestions
        self.suggestion_scroll.setVisible(False)

        # Mise à jour interne
        self.current_project_name = selected_name
        self.current_project_folder = str(selected_folder)

        # Lancer ton workflow existant
        self.set_projectFolder(self.current_project_folder)

    def add_project_clicked(self):

        folder_path = create_new_folder(
            project_name=self.current_project_name,
            parent_widget=self.dockwidget,
            log=None,
            dockwidget=self.dockwidget,
            iface=self.iface)

        if folder_path and os.path.isdir(folder_path):
            self.set_projectFolder(folder_path)
        else:
            print("Création du dossier annulée ou invalide.")



    def gest_style(self):
        path = QFileDialog.getExistingDirectory(self.dockwidget, "Select stylesDirectory")
        if path:
            print("Selected directory:", path)
            self.current_style_folder = path
        else:
            print("No directory selected")
            self.current_style_folder = None
        
        
        self.current_style_folder = path

        if self.dockwidget:
            self.dockwidget.current_style_folder = self.current_style_folder
            if hasattr(self.dockwidget, "tools_tab"):
                self.dockwidget.tools_tab.current_style_folder = self.current_style_folder




    def open_global_settings(self):
        self.global_settings_dialog = GlobalSettingsDialog(plugin=self)
        self.global_settings_dialog.show()

        
    def open_connect_label(self):
        self.connect_dialog = connect_label(plugin=self)
        self.connect_dialog.show()


    def get_watchdog_context(self):
        """
        Fournit au watchdog l'état courant du plugin
        """
        return {
            "project_name": self.current_project_name,
            "project_folder": self.current_project_folder,
            "downloads_path": self.downloads_path,
            "style_folder": self.current_style_folder,
            "watch_mode": self.watch_mode}
    



