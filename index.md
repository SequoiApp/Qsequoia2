# QSequoia2

<link rel="icon" type="image/png" href="assets/img/favicon.ico">

## Bienvenue dans QSequoia2

**QSequoia2** est un plugin **QGIS** conçu pour simplifier et structurer les données forestières.

Il fournit un ensemble d’outils pour :

* l’import
* la visualisation
* la mise en forme
* l’analyse

des couches vecteur et raster générées par le package **Rsequoia2**, ainsi que l’accès à des services web géospatiaux (**WMTS/WMS**).

---

## Objectif

Conçu pour **QGIS 3.44**, le plugin, développé par des forestiers pour des forestiers, permet, que l’on soit familier avec l’art de la cartographie ou cartographe du dimanche, d’utiliser un outil *gratuit* et *open source*, simple d’utilisation et adapté à tous types de forestiers.

Il combine :

* automatisation
* flexibilité
* respect des standards SIG

---

## Fonctionnalités principales

### Import de données

* Import rapide des couches générées par **Rsequoia2** et des couches WMTS/WMS utiles au milieu forestier
* Création automatique des projets thématiques et de leurs mises en page
* Affichage des données
* Vérification et aide au remplissage des unités d’analyse
* Organisation par catégories métiers

---

### Application automatique de styles et de mises en page

* Bibliothèque de styles et de mises en page configurable
* Rendu homogène et standardisé

---

### Organisation des projets

* Intégration automatique des données
* Création de groupes thématiques
* Vérifications topologiques avancées
* Arborescence claire et structurée

---

# Installation

> ⚠️ Le plugin est en cours de développement et n’est pas encore disponible sur le dépôt officiel QGIS.

## Téléchargement

### Pré-requis

* QGIS 3.44 ou supérieur

---

### Installation

Allez dans :

![installation1](../assets/img/qgis_extentsions.png)

Cliquez sur **Ajouter** dans **Dépôts d’extensions**, puis :

![installation2](../assets/img/qgis_param_ext.png)

Entrez le lien vers le fichier `XML` du dépôt **SEQUOIAPP** :

https://raw.githubusercontent.com/SequoiApp/Qsequoia2/main/plugins.xml

![installation3](../assets/img/qgis_ajout_depot.png)

Une fois le lien enregistré et le dépôt connecté, vous pouvez rechercher **QSequoia2** dans les extensions et installer le plugin.

**PS :** N’oubliez pas d’activer les extensions expérimentales.

Une fois installé, vous pouvez utiliser le plugin.

Les mises à jour sont fréquentes : pensez à vérifier régulièrement la page des extensions installées.

![installation4](../assets/img/qgis_maj_plugin.png)

---

# Modules principaux

* [Menu principal](mod/modules.html#main)
* [Paramètres globaux](mod/modules.html#global)
* [Données sur la propriété](mod/modules.html#dash)
* [Vérificateurs et sélecteur d’entités](mod/modules.html#dash)
* [Ajout de données](mod/modules.html#add_data)
* [Projets thématiques et mises en page](mod/modules.html#project)
* [Outils](mod/modules.html#tools)

---

# Auteurs

* Alexandre Le Bars — Comité des Forêts
  [alexlb329@gmail.com](mailto:alexlb329@gmail.com)

* Paul Carteron — Racines Experts Forestiers Associés
  [carteronpaul@gmail.com](mailto:carteronpaul@gmail.com)

* Matthieu Chevereau — Caisse des Dépôts
  [matthieu.chevereau@hotmail.fr](mailto:matthieu.chevereau@hotmail.fr)

---

# Liens utiles

* https://github.com/SequoiAPP
* https://github.com/SequoiAPP/qsequoia2/issues

---

# © Licence

© 2025 QSequoia2 — Tous droits réservés
