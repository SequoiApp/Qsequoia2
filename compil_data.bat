
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
