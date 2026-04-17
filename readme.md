# QSequoia2

<img src="qsequoia2/icons/Qsequoia2.png" align="right" height="120"/>

## 🇫🇷 Présentation

**QSequoia2** est un plugin QGIS dédié à la gestion, la structuration et la visualisation des données forestières.

Développé par des forestiers pour des forestiers, il permet d’automatiser l’import, l’organisation et la mise en forme des données issues de **RSequoia2**.

---

## 🇬🇧 Overview

**QSequoia2** is a QGIS plugin designed for managing, structuring, and visualizing forest data.

Developed by foresters for foresters, it automates data import, organization, and styling from **RSequoia2**.

---

# 🇫🇷 Fonctionnalités

* Intégration des données issues de **RSequoia2**
* Organisation des couches par thématique métier
* Application automatique de styles et de mises en page
* Création de projets QGIS structurés
* Vérification des données (unités d’analyse)
* Accès aux services web cartographiques (WMTS/WMS/TMS)

---

# 🇬🇧 Features

* Integration of **RSequoia2** outputs
* Layer organization by thematic groups
* Automatic styling and layout generation
* Structured QGIS project creation
* Data validation (analysis units)
* Access to web map services (WMTS/WMS/TMS)

---

# 🇫🇷 Prérequis

* QGIS 3.44 ou supérieur
* Accès à Internet

---

# 🇬🇧 Requirements

* QGIS 3.44 or higher
* Internet access

---

# 🇫🇷 Installation

## Méthode recommandée : dépôt QGIS

1. Ouvrir QGIS
2. Aller dans **Extensions > Installer/Gérer les extensions**
3. Onglet **Paramètres > Dépôts d’extensions**
4. Ajouter le dépôt :

```id="v8qj0x"
https://raw.githubusercontent.com/SequoiApp/Qsequoia2/main/plugins.xml
```

5. Activer les **extensions expérimentales**
6. Rechercher **QSequoia2**
7. Installer le plugin

---

## Installation manuelle

1. Télécharger la dernière version :
   https://github.com/SequoiApp/QSEQUOIA-2/releases

2. Décompresser dans :

```id="0q0xhh"
%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins
```

3. Redémarrer QGIS
4. Activer le plugin

---

# 🇬🇧 Installation

## Recommended method: QGIS repository

1. Open QGIS
2. Go to **Plugins > Manage and Install Plugins**
3. Tab **Settings > Plugin repositories**
4. Add repository:

```id="4n08kx"
https://raw.githubusercontent.com/SequoiApp/Qsequoia2/main/plugins.xml
```

5. Enable **experimental plugins**
6. Search for **QSequoia2**
7. Install the plugin

---

## Manual installation

1. Download latest release:
   https://github.com/SequoiApp/QSEQUOIA-2/releases

2. Extract to:

```id="t1o0my"
%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins
```

3. Restart QGIS
4. Enable the plugin

---

# 🇫🇷 Utilisation

* Accès via le menu QGIS
* Sélection d'un dossier `Sequoia2`
* Import des données `Sequoia2`
* Organisation en groupes thématiques 
* Application automatique des styles et mises en page

---

# 🇬🇧 Usage

* Available from QGIS menu
* Select `Sequoia` folder
* Automatic `Sequoia` data import
* Thematic layer organization
* Automatic styling and layout generation

---

# 🇫🇷 Développement

## Workflow Git

* Développement sur branches
* Pull request obligatoire
* Branche `main` = versions stables

## Build automatique

Lors d’un merge vers `main` :

* Compilation automatique
* Génération du ZIP
* Publication d’une release

---

# 🇬🇧 Development

## Git workflow

* Development on branches
* Pull requests required
* `main` branch for stable releases

## Automated build

On merge to `main`:

* Plugin compilation
* ZIP generation
* GitHub release publication

---

# Authors

* Alexandre Le Bars — Comité des Forêts
* Paul Carteron — Racines Experts Forestiers Associés
* Matthieu Chevereau — Caisse des Dépôts

---

# Links

* https://github.com/SequoiAPP
* https://github.com/SequoiAPP/QSEQUOIA-2
* https://github.com/SequoiAPP/qsequoia2/issues

---

# Licence / License

© 2025 QSequoia2 — All rights reserved
