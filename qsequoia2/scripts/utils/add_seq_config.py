"""
Module `seq_config` : gestion du téléchargement et de la mise à jour
des fichiers de configuration YAML pour RSequoia2 depuis le dépôt distant.

Auteur : Alexandre Le Bars - Comité des Forêts
Email : alexlb329@gmail.com

Fonctionnalités :
- Téléchargement automatique des fichiers YAML de configuration à chaque démarrage du plugin
- Remplacement des fichiers locaux si différents de la version distante
"""


#---------------------------------------------------------------------------------

import os
import urllib.request
import yaml
from qgis.PyQt.QtWidgets import QMessageBox

from ..utils.messageBar import *

#---------------------------------------------------------------------------------


def add_seq_config():
    """
    Télécharge et met à jour les fichiers de configuration RSequoia2 depuis le dépôt distant.

    Processus :
    1. Récupère le dossier local 'inst' du plugin.
    2. Lit le fichier `URLs.yaml` contenant les URLs des fichiers YAML à mettre à jour.
    3. Télécharge chaque fichier YAML depuis le dépôt distant.
    4. Écrit le fichier localement, remplaçant la version existante si nécessaire.
    5. Affiche des messages d'erreur via QMessageBox en cas de problème réseau ou d'écriture.
    
    Notes :
        - Le téléchargement est fait via urllib.request.
        - Les fichiers YAML sont stockés dans le dossier `inst` du plugin.
        - Les erreurs critiques affichent un message utilisateur et continuent le traitement des autres fichiers.
    """
    
    # Récupération du dossier de configuration de QSequoia2

    script_path = os.path.dirname(os.path.abspath(__file__))
    inst = os.path.abspath(os.path.join(script_path, '..', '..', 'inst'))

    # Lecture du YAML des URLs 

    urls_yaml_path = os.path.join(inst, 'URLs.yaml')
    with open(urls_yaml_path, 'r', encoding='utf-8') as file:
        urls_data = yaml.safe_load(file)
    seq_layers_url = urls_data['seq_layers']['url']

    # Connexion au dépôt GitHub pour récupérer les fichiers YAML

    for key, entry in urls_data.items():

        # Récupération de l’URL dans le sous-dictionnaire
        url = entry.get("url")
        if not url:
            continue

        try:
            response = urllib.request.urlopen(url)
            remote_yaml_content = response.read().decode('utf-8')
        except Exception as e:
            QMessageBox.critical(None, "Erreur réseau",
                                f"Impossible de télécharger {key}.yaml.\nErreur : {e}")
            continue

        local_yaml_path = os.path.join(inst, f"{key}.yaml")

        try:
            with open(local_yaml_path, 'w', encoding='utf-8') as local_file:
                local_file.write(remote_yaml_content)
        except Exception as e:
            QMessageBox.critical(None, "Erreur d'écriture",
                                f"Impossible d'écrire {key}.yaml.\nErreur : {e}")
            return
        
        # Message de confirmation dans les logs de QGIS

    messageLog("Les fichiers de configuration RSequoia2 ont été mis à jour avec succès.","i")


