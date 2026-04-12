

# Qsequoia2 <img src="qsequoia2/icons/Qsequoia.png" align="right" height="138"/>

<!-- badges: start -->
📥 download the latest version

👉 [download the beta plugin version (release)](https://github.com/SequoiApp/QSEQUOIA-2/releases)
<!-- badges: end -->




## Comment Installer ?

Après le téléchargement, tapez sur la touche 🪟, puis tapez : 
```
%appdata%
```
puis rendez-vous ici -> **"\QGIS\QGIS3\profiles\default\python\plugins"** 

Copiez-y le dossier **qsequoia2**, relancez QGIS et activez le plugin dans la page des extensions installées.








## QSEQUOIA2 — Workflow Git & Build

Règles de contribution

Tous les commits doivent être faits sur une branche local.
Une fois les modifications terminé, veuillez executer un `pull request` et attendre une validation par l'un des membres
La branche MAIN est réservée aux versions stables et aux releases automatiques.

Build automatique (GitHub Actions)
Dès qu’un merge de DEV vers MAIN est effectué :
- Le workflow build-release se déclenche automatiquement
- Le plugin est compilé
- Un ZIP propre est généré (qsequoia2/ + CHANGELOG.md)
- Une nouvelle release GitHub est créée avec un tag basé sur la date du jour
Aucune action manuelle n’est nécessaire.

Tester le plugin en local (Windows uniquement)

Avant de commit, tester le plugin QGIS local.

Script BATCH (Windows)

```BATCH
###For local test

@echo off
REM === Définir les chemins ===
### Note: Please adjust the paths below to match your project and QGIS plugin directory ###
set SRC_DIR="<repo folder path>"
set DEST_DIR="<chemin vers dossier des plugins>"

REM === Copier le dossier du projet ===
echo Copie du projet en cours...
xcopy %SRC_DIR% %DEST_DIR% /E /H /Y
echo Copie terminée.

REM === Charger les environnements QGIS ===
### Note: Please adjust the paths below to match your QGIS installation directory ###
call "<chemin vers QGIS>\QGIS\bin\o4w_env.bat"
call "<chemin vers QGIS>\QGIS\bin\qt5_env.bat"
call "<chemin vers QGIS>\QGIS\bin\py3_env.bat"

@echo on

REM === Compiler le fichier resources.qrc en resources.py ===
cd %DEST_DIR%
pyrcc5 -o resources.py resources.qrc

echo Compilation terminée
pause

###ALB
```






