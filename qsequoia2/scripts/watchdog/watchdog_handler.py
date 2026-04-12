"""
watchdog_handler.py
===================

Handler pour le DogWatcher de QSEQUOIA2.

Surveille la création et le déplacement des fichiers ZIP dans les dossiers
suivis par le DogWatcher et les ajoute à la file d'attente de traitement.

Auteur : Alexandre Le bars - Comité des forêts
Date   : 2026-01-20
"""
import sys, os

script_dir = os.path.dirname(__file__)
watchdog_path = os.path.join(script_dir, '..','..','inst','lib')
sys.path.insert(0, watchdog_path)

from watchdog.events import FileSystemEventHandler

class DownloadEventHandler(FileSystemEventHandler):
    """
    Gestionnaire d'événements pour le DogWatcher.

    Surveille les fichiers ZIP créés ou déplacés et les ajoute à la liste
    `pending_zips` du DogWatcher pour traitement ultérieur.
    """

    def __init__(self, watcher):
        """
        Initialisation du handler.

        :param watcher: instance de DogWatcher à notifier des événements
        """
        super().__init__()
        self.watcher = watcher  # référence vers le DogWatcher

    # ----------------------------------------------------------------------
    def on_created(self, event):
        """
        Appelé lorsqu'un fichier ou un dossier est créé dans le dossier surveillé.

        :param event: événement de création (FileSystemEvent)
        """
        if event.is_directory:
            return  # ignorer les dossiers
        if event.src_path.lower().endswith(".zip"):
            print(f"[watchdog] Nouveau ZIP détecté : {event.src_path}")
            self.watcher.pending_zips.append(event.src_path)

    # ----------------------------------------------------------------------
    def on_moved(self, event):
        """
        Appelé lorsqu'un fichier ou dossier est déplacé dans le dossier surveillé.

        :param event: événement de déplacement (FileSystemEvent)
        """
        if event.is_directory:
            return  # ignorer les dossiers
        if event.dest_path.lower().endswith(".zip"):
            print(f"[watchdog] ZIP déplacé : {event.dest_path}")
            self.watcher.pending_zips.append(event.dest_path)
