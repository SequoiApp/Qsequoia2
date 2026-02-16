import os
from qgis.core import QgsVectorLayer, QgsWkbTypes

project_folder = r"E:\GEO_DEV_SIG\projet\STFRANCHY_SEQ_project"
layer_paths = {'COMS_TOPO_line': 'E:/GEO_DEV_SIG/projet/STFRANCHY_SEQ_project\\LAYOUT\\VECTORIEL\\COMS_TOPO_line.gpkg'}


for path in layer_paths.values():
    print("Chemin:", path)
    print("Upper:", path.upper())
    print('"LAYOUT" in path.upper():', "LAYOUT" in path.upper())

if layer_paths and any("LAYOUT" not in path.upper() for path in layer_paths.values()):
    print("LAYOUT not found in paths, je lance load vecteurs")
else:
    print("Toutes les couches contiennent LAYOUT")

