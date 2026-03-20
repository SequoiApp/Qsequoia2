"""
Lecture de l'excel final et affichage des données
"""

# ===============================================
# region import
# ===============================================


import os

from qgis.core import *
from PyQt5.QtCore import QVariant
import processing
# endregion

# ==============================================
# region getFinaldata
# ==============================================


# class getFinaldata():
table = r'E:/GEO_DEV_SIG/projet/LE_NIVOT_SEQ_SIG/SYNTHESE_20260315T185922.xlsx'
couche = [
    "PF_RICH",
    "PF_PLT",
    "PENTE",
    "MNT",
    "MNH",
    "EXPO"]



sortie = "memory"

numeric_types = [QVariant.Double, QVariant.Int, QVariant.LongLong]

for layers in couche :
    use = table + "|layername=" + layers
    layer_excel = QgsVectorLayer(use, "", "ogr")

    fields = [f.name() for f in layer_excel.fields()]

    # exclure certains champs
    exclude = ['fid', 'N_PARFOR']
    fields_to_keep = [f for f in fields if f not in exclude]

    result = processing.run("native:joinattributestable", 
                {'INPUT':'E:/GEO_DEV_SIG/projet/LE_NIVOT_SEQ_SIG/1_SEQUOIA/LE_NIVOT_SEQ_PF_poly.gpkg',
                    'FIELD':'N_PARFOR',
                    'INPUT_2': use,
                    'FIELD_2':'N_PARFOR',
                    'FIELDS_TO_COPY': fields_to_keep, 
                    'METHOD':0,
                    'DISCARD_NONMATCHING':False,
                    'PREFIX': layers + "_",
                    'OUTPUT': "memory:"
                }
            )

    input_layer = result['OUTPUT']

# résultat final
final_layer = input_layer

QgsProject.instance().addMapLayer(final_layer)