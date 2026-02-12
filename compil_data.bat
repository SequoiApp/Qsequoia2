
@echo off
REM === Définir les chemins ===
### Note: Please adjust the paths below to match your project and QGIS plugin directory ###
set SRC_DIR="C:\Users\alexl\Desktop\balrog\PROJETS\SEQUOIAPP\REPOS\QSEQUOIA2\qsequoia2"
set DEST_DIR="C:\Users\alexl\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\qsequoia2"

REM === Copier le dossier du projet ===
echo Copie du projet en cours...
xcopy %SRC_DIR% %DEST_DIR% /E /H /Y
echo Copie terminée.

REM === Charger les environnements QGIS ===
### Note: Please adjust the paths below to match your QGIS installation directory ###
call "C:\Users\alexl\Desktop\sylviculture et GF\3.cartographie-SIG\Devellopement\QGIS\bin\o4w_env.bat"
call "C:\Users\alexl\Desktop\sylviculture et GF\3.cartographie-SIG\Devellopement\QGIS\bin\qt5_env.bat"
call "C:\Users\alexl\Desktop\sylviculture et GF\3.cartographie-SIG\Devellopement\QGIS\bin\py3_env.bat"

@echo on

REM === Compiler le fichier resources.qrc en resources.py ===
cd %DEST_DIR%
pyrcc5 -o resources.py resources.qrc

echo Compilation terminée !
pause
