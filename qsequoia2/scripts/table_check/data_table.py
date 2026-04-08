from qgis.core import *
from PyQt5.QtCore import QVariant
from pathlib import Path
import processing

# ==============================================
# region getFinaldata
# ==============================================

def getFinaldata(synthese):
    """joint les données finalisé par parcelle dans une seule et même table
        sous forme d'un layers vecteur temporaire
        args : 
        - synthesePath : (str) chemin vers le fichier excel"""
    # Tables à parcourir
    couche = [
        "PF",
        "PF_RICH",
        "PF_PLT",
        "PENTE",
        "MNT",
        "MNH",
        "EXPO"]
    
    # definir le nombre de table dans la liste
    nbcouche = len(couche)
    table = 1
    # on prend le premier élément comme base 
    baselistelem = couche[0]
    numeric_types = [QVariant.Double, QVariant.Int, QVariant.LongLong]
    baseLayer = QgsVectorLayer(synthese + "|layername=" + baselistelem,"base","ogr")

    while table < nbcouche :
        # récupération des nom de table en fonction du numéro dans la liste
        listelem = couche[table]

        use = synthese + "|layername=" + listelem

        layer_excel = QgsVectorLayer(use, "", "ogr")

        fields = [f.name() for f in layer_excel.fields()]

        # exclure le champ N_PARFOR (déja présent)
        exclude = ['N_PARFOR']
        fields_to_keep = [f for f in fields if f not in exclude]

        # Lancer l'algo processing
        result = processing.run("native:joinattributestable", 
                    {'INPUT': baseLayer,
                        'FIELD':'N_PARFOR',
                        'INPUT_2': use,
                        'FIELD_2':'N_PARFOR',
                        'FIELDS_TO_COPY': fields_to_keep, 
                        'METHOD':0,
                        'DISCARD_NONMATCHING':False,
                        'PREFIX': listelem + "_",
                        'OUTPUT': "memory:"
                    }
                )
        
        # définir la nouvelle couche à utiliser pour la suite du traitement
        baseLayer = result['OUTPUT']
        # on ajoute 1 a table pour qu'il joigne la prochaine couche de la liste à celle générer ici
        table += 1

    return baseLayer



# endregion
# ================================================
# region vérificateur
# ================================================

# Calcul des surfaces par parcelles ou sous parcelles séléctionné

def sspf_surface_calculation(ua_layer) -> str:

    feats = list(ua_layer.getSelectedFeatures())
    if not feats: return "0 ha"
    tmp = QgsVectorLayer("Polygon?crs=" + ua_layer.crs().authid(), "tmp", "memory")
    tmp.dataProvider().addFeatures(feats)
    surf = sum(f.geometry().area() for f in tmp.getFeatures()) / 10000
    return f"{round(surf,4)} ha"

    

