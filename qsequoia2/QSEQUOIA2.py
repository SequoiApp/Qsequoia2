import sys
from pathlib import Path
import os

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction

from qsequoia2.scripts.global_settings.global_settings import GlobalSettingsDialog
from qsequoia2.scripts.watchdog.dogwatcher import DogWatcher
from qsequoia2.scripts.utils.get_download_folder import get_download_folder
from qsequoia2.scripts.utils.seq_config import sync_seq_configs
from qsequoia2.scripts.utils.messageBar import messageLog
from qsequoia2.scripts.utils.reloader import reloadQS2
from qsequoia2.scripts.utils.variable import *
from qsequoia2.scripts.utils.qgz_project import *

from .qsequoia2_dockwidget import Qsequoia2DockWidget

PLUGIN_DIR = Path(__file__).resolve().parent
ICONS_DIR = PLUGIN_DIR / "icons"

watchdog_path = str(PLUGIN_DIR / "inst" / "lib")
if watchdog_path not in sys.path:
    sys.path.insert(0, watchdog_path)

class Qsequoia2:

    def __init__(self, iface):
        self.iface = iface

        # Locale
        locale_value = QSettings().value('locale/userLocale', 'en')
        locale = str(locale_value or "en")[:2]

        locale_path = PLUGIN_DIR / 'i18n' / f'Qsequoia2_{locale}.qm'

        if locale_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(locale_path))
            QCoreApplication.installTranslator(self.translator)

        # UI
        self.actions = []
        self.menu = self.tr("&Qsequoia2")
        self.toolbar = None
        self.dockwidget = None
        self.dlg = None

        # Watchdog
        self.watch_mode = "auto"
        self.downloads_path = get_download_folder()
        self.connect_dialog = None
        self.dogwatcher = None 

    def tr(self, message):
        return QCoreApplication.translate('Qsequoia2', message)

    def initGui(self):

        self.toolbar = self.iface.addToolBar("Qsequoia2")
        self.toolbar.setObjectName("Qsequoia2")

        icon_path = ICONS_DIR / "Qsequoia2.svg"

        action = QAction(QIcon(str(icon_path)), self.tr("Qsequoia2"), self.iface.mainWindow())
        action.triggered.connect(self.run)

        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        # Fetch Rsequoia2 config
        sync_seq_configs()

        # Lazy init watchdog
        if self.dogwatcher is None:
            self.dogwatcher = DogWatcher(
                iface=self.iface,
                get_context_callback=self.get_watchdog_context,
                parent=None
            )

    def run(self):

        # Handle DockWidget
        ## If already created
        if self.dockwidget:
            self.dockwidget.show()
            self.dockwidget.raise_()
            return

        ## Else: create
        self.dockwidget = Qsequoia2DockWidget(iface=self.iface)

        self._connect_dockwidget()

        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)

    def _connect_dockwidget(self):

        dw = self.dockwidget

        dw.closingPlugin.connect(self._on_closed_plugin)
        dw.projectChanged.connect(self._on_project_changed)

        dw.btn_sequoia.clicked.connect(self._open_sequoia_website)
        dw.btn_settings.clicked.connect(self._open_global_settings)
        dw.btn_reload.clicked.connect(self._reload_plugin)
        dw.btn_open_seq_dir.clicked.connect(self._open_seq_dir)
        dw.btn_issue.clicked.connect(self._open_qsequoia_issue)
    
    def _on_closed_plugin(self):
        """Cleanup when dockwidget is closed"""

        if self.dockwidget:
            try:
                self.dockwidget.closingPlugin.disconnect(self._on_closed_plugin)
            except Exception:
                pass

            self.dockwidget = None

    def _on_project_changed(self, seq_dirname, seq_dir, seq_identifier):
        """Handle project selection from UI"""

        set_project_variable("QS2_seq_dirname", seq_dirname)
        set_project_variable("QS2_seq_dir", seq_dir)
        set_project_variable("QS2_seq_identifier", seq_identifier)

        messageLog(f"SEQ_DIRNAME: {seq_dirname}", "i")
        messageLog(f"SEQ_DIR: {seq_dir}", "i")

        # TODO corriger le bug des nom de projet définit des le lancement selon la proposition de projet

        seq_qgz_project = str(get_global_variable("QS2_default_project")).strip().lower()

        if seq_qgz_project == "true":
            if self.dockwidget.cb_seq_folder.currentText() == seq_dirname:
                find_qgis_project(seq_dir, seq_dirname)


    def _open_global_settings(self):
        """Ouvre la fenêtre de configuration globale du plugin."""
        self.global_settings_dialog = GlobalSettingsDialog(iface=self.iface, plugin=self)
        if self.dockwidget:
            self.global_settings_dialog.settingsUpdated.connect(
                self.dockwidget.refresh
            )
        self.global_settings_dialog.show()

    def _reload_plugin(self):
        """Reload plugin (wrapped for clarity)"""
        reloadQS2(self.iface)

    def _open_seq_dir(self):

        seq_dir = get_project_variable("QS2_seq_dir") or ""
        if not seq_dir:
            return

        path = Path(seq_dir)
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_sequoia_website(self):
        url = QUrl("https://sequoiapp.github.io/Rsequoia2/index.html")
        QDesktopServices.openUrl(url)
    
    def _open_qsequoia_issue(self):
        url = QUrl("https://github.com/SequoiApp/Qsequoia2/issues")
        QDesktopServices.openUrl(url)
        
    def unload(self):

        # Remove actions
        for action in getattr(self, "actions", []):
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        # Remove toolbar
        if hasattr(self, "toolbar") and self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar = None

        # Remove translator
        if hasattr(self, "translator"):
            QCoreApplication.removeTranslator(self.translator)

    def get_watchdog_context(self):
        """
        Retourne l'état courant du plugin utilisé par le système de surveillance (watchdog).

        Les informations retournées incluent :
        - le nom du projet actif,
        - le dossier du projet,
        - le dossier des téléchargements,
        - le dossier des styles,
        - le mode de surveillance utilisé.
        """

        return {
            "project_name": self.current_project_name,
            "project_folder": self.current_project_folder,
            "downloads_path": self.downloads_path,
            "style_folder": self.current_style_folder,
            "watch_mode": self.watch_mode
        }
    


    # ## fonction set_projectFolder
    # def set_projectFolder(self, path=None):
    #     """
    #     Définit le dossier de projet actif.

    #     Cette fonction permet :
    #     - de sélectionner manuellement un dossier de projet si aucun chemin n'est fourni,
    #     - de déterminer automatiquement le nom du projet à partir des fichiers ou du nom du dossier,
    #     - de mettre à jour les variables internes du plugin (nom et chemin du projet),
    #     - de propager ces informations aux différents onglets du DockWidget,
    #     - de redémarrer les mécanismes de surveillance (watchdog),
    #     - de charger ou créer un projet QGIS (.qgz) si nécessaire,
    #     - de vérifier la présence de données forestières (PARCA) et lancer les calculs associés si disponibles.
    #     """

    #     ### Selection des dossiers manuellement 

    #     if path is None : # passe dans le cas ou un dossier de projet est créée
    #         path = QFileDialog.getExistingDirectory(self.dockwidget, "Select project Directory")

    #         if not path:
    #             self.current_project_folder = None
    #             self.current_project_name = None
    #             return

    #     messageLog(f"Selected directory: {path}","i")
    #     self.current_project_folder = path
    #     # SI chemin, on masque les suggestion de projet
    #     if path:

    #         self.suggestion_list.clear()
    #         self.suggestion_list.setVisible(False)
    #         self.suggestion_scroll.setVisible(False)
    #     # on grise le boutton add_project
    #     self.dockwidget.add_project.setEnabled(False)


    #     # extraction du nom du projet

    #     project_name = None

    #     # test pour trouver le nom d eprojet depuis des fichiers
    #     for root, dirs, files in os.walk(self.current_project_folder):
    #         for filename in files:

    #             if "_matrice" in filename:
    #                 project_name = filename.split("_matrice")[0]
    #                 break

    #             if "_SEQ_PARCA_poly" in filename:
    #                 project_name = filename.split("_SEQ_PARCA_poly")[0]
    #                 break

    #             if "_SEQ_PROJECT" in filename:
    #                 project_name = filename.split("_SEQ_PROJECT")[0]

    #         if project_name:
    #             break

    #     # fallback sur le dossier de projet si rien trouvé
    #     if not project_name:
    #         folder_name = os.path.basename(self.current_project_folder)
    #         if "_SIG" in folder_name:
    #             project_name = folder_name.split("_SIG")[0]
    #         if "_SEQ" in folder_name:
    #             project_name = folder_name.split("_SEQ")[0]
    #         if "SEQ_SIG" in folder_name:
    #             project_name = folder_name.split("_SEQ_SIG")[0]

    #         # Pour les anciennes couches et anciens projets
    #         if folder_name == "SIG":
    #             for nom in os.listdir(self.current_project_folder):
    #                 if "SEQ_PARCA_poly" in nom:
    #                     continue
    #                 if "PARCA" in nom:
    #                     project_name = nom.split("_PARCA")[0]
    #                     break

    #     if not project_name:
    #         project_name, ok = QInputDialog.getText(None,"Nom du projet", "Impossible de déterminer le nom du projet.\nVeuillez saisir le nom du projet :")

    #         if not ok or not project_name.strip():
    #             self.current_project_folder = None
    #             raise Exception("Nom du projet non fourni. Opération annulée.")

    #     self.current_project_name = project_name

    #     # --- Propagation au DockWidget ---
    #     if self.dockwidget:
    #         self.dockwidget.current_project_name = self.current_project_name
    #         self.dockwidget.current_project_folder = self.current_project_folder

    #         # Afficher uniquement le nom du projet dans le champ
    #         self.dockwidget.cb_seq_folder.blockSignals(True)
    #         self.dockwidget.cb_seq_folder.setText(self.current_project_name)
    #         self.dockwidget.cb_seq_folder.blockSignals(False)
    #         self.dockwidget.cb_seq_folder.setEnabled(False)

    #         # Propager aux onglets
    #         if hasattr(self.dockwidget, "tools_tab"):
    #             self.dockwidget.tools_tab.current_project_name = self.current_project_name
    #             self.dockwidget.tools_tab.current_project_folder = self.current_project_folder

    #         if hasattr(self.dockwidget, "data_settings_tab"):
    #             self.dockwidget.data_settings_tab.current_project_name = self.current_project_name
    #             self.dockwidget.data_settings_tab.current_project_folder = self.current_project_folder
            
    #         if hasattr(self.dockwidget, "LayoutDesigner_tab"):
    #             self.dockwidget.LayoutDesigner_tab.current_project_name = self.current_project_name
    #             self.dockwidget.LayoutDesigner_tab.current_project_folder = self.current_project_folder
            
    #         if hasattr(self.dockwidget, "forest_data_tab"):
    #             self.dockwidget.forest_data_tab.current_project_name = self.current_project_name
    #             self.dockwidget.forest_data_tab.current_project_folder = self.current_project_folder
            
    #         # --- Propagation aux addons chargés ---
    #         if hasattr(self.dockwidget, "addons_tabs"):
    #             for addon in self.dockwidget.addons_tabs:
    #                 addon.current_project_name = self.current_project_name
    #                 addon.current_project_folder = self.current_project_folder


    #     # Mise à jour éventuelle du connect_dialog
    #     if self.connect_dialog:
    #         self.connect_dialog.update_watch_path_label()

    #     # redémarrer le watcher
    #     if self.dogwatcher:
    #         self.dogwatcher.restart()

    #         messageLog(f"Project name => {self.current_project_name}", "i")
        
    #     # Vérifier si dossier contient un projet QGZ, si non, on le crée, uniquement si variable utilisateur

    #     project = QgsProject.instance()

    #     if self.QSS2_default_project == "true" or True :
    #         project_path = ensure_and_load_qgis_project(
    #             project,
    #             project_folder=self.current_project_folder,
    #             project_name=self.current_project_name,
    #             epsg="EPSG:2154")
            
    #         messageLog(f"Projet QGZ chargé : {project_path}", "i")
        
    #     messageBar(self.iface, f"Dossier {self.current_project_name} sélectionné avec succès : {self.current_project_folder}","s",10)
        
    #     # Vérifier s'il y a une couche PARCA dans le dossier projet

    #     parca_files = any("PARCA" in name.upper()for root, dirs, files in os.walk(self.current_project_folder)for name in dirs + files)
        
    #     # Si une couche Parca existe, on lance le calcul des metadonnées de bases

    #     if not parca_files:
    #         messageLog("Aucune couche PARCA trouvée dans le dossier du projet. Calcul forestier annulé.","w")
    #     else:
    #         try:
    #             forest_data = getForestdata(
    #                 project_name=project_name,
    #                 project_folder=self.current_project_folder,
    #                 style_folder=self.current_style_folder,
    #                 iface=self.iface)
                
    #             forest_data.run_all_calculations()
    #         except Exception as e:
    #             messageLog(f"Erreur lors du calcul des metadata : {e}","w")

    # ## on_project_name_changed
    # def on_project_name_changed(self, text):
    #     """
    #     Gère les modifications du nom de projet saisies par l'utilisateur.

    #     Cette fonction :
    #     - met à jour le nom du projet courant,
    #     - propose automatiquement des dossiers de projet existants correspondant au texte saisi,
    #     - affiche une liste de suggestions si des correspondances sont trouvées,
    #     - active ou désactive le bouton de création de projet selon la validité du texte,
    #     - propage le nom du projet aux composants du DockWidget,
    #     - redémarre le système de surveillance si nécessaire.
    #     """

    #     # si le changement vient du code → on ignore
    #     if self.updating_project_name:
    #         return

    #     self.current_project_name = text

    #     # Activation du bouton
    #     text_clean = text.strip()
    #     text_valid = bool(text_clean)  # vrai uniquement si texte non vide

    #     # Propager au DockWidget
    #     if self.dockwidget:
    #         self.dockwidget.current_project_name = self.current_project_name
    #         self.dockwidget.cb_seq_folder.blockSignals(True)
    #         self.dockwidget.cb_seq_folder.setText(self.current_project_name)
    #         self.dockwidget.cb_seq_folder.blockSignals(False)

    #         # Propager aux onglets si nécessaire
    #         if hasattr(self.dockwidget, "tools_tab"):
    #             self.dockwidget.tools_tab.current_project_name = self.current_project_name
            
    #         if hasattr(self.dockwidget, "data_settings_tab"):
    #             self.dockwidget.data_settings_tab.current_project_name = self.current_project_name


    #     if text:  # éviter de lancer sur vide
    #         if self.dogwatcher:
    #             self.dogwatcher.restart()

    #         else:
    #             messageLog("Watcher non initialisé, rien à redémarrer.","w")

    # ## add_project_clicked
    # def add_project_clicked(self):
    #     """
    #     Crée un nouveau dossier de projet à partir du nom saisi par l'utilisateur.

    #     Si la création du dossier réussit :
    #     - le dossier est défini comme dossier de projet actif,
    #     - le processus de chargement du projet est lancé.

    #     Si la création est annulée ou échoue, aucune modification n'est appliquée.
    #     """

    #     folder_path = create_new_folder(
    #         project_name=self.current_project_name,
    #         parent_widget=self.dockwidget,
    #         log=None,
    #         dockwidget=self.dockwidget,
    #         iface=self.iface)

    #     if folder_path and os.path.isdir(folder_path):
    #         self.set_projectFolder(folder_path)

    # ## get_watchdog_context
 

