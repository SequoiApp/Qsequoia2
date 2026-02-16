import os
from qgis.core import QgsVectorLayer, QgsWkbTypes

project_folder = r"E:\GEO_DEV_SIG\projet\STFRANCHY_SEQ_project"
label = "SEQ_PARCA_poly"
# Fonction utilitaire de get_path pour trouver les couches

def find_best_layer_qgis(project_folder, label):
    """
    Recherche optimisée d'une couche vectorielle ou raster dans le dossier projet.

    Supporte :
        - vecteurs : shp, gpkg, geojson
        - rasters : tif, img

    Args:
        project_folder (str): dossier du projet
        label (str): label YAML (ex: 'SEQ_PARCA_poly')
        max_candidates (int, optional): nombre max de fichiers candidats à vérifier

    Returns:
        str | None: chemin du fichier trouvé, ou None si aucun
    """

    label = label.lower()
    parts = label.split("_")
    
    print(parts)

    expected_geom = None
    if parts[-1] in ("poly", "line", "point"):

        expected_geom = parts[-1]
        if expected_geom == "polygon":
            expected_geom = "poly"
        parts = parts[:-1]

    expected_tokens = parts

    print(f"expected_geom: {expected_geom}")
    print(f"expected_tokens: {expected_tokens}")

    # Extensions supportées
    vector_exts = (".shp", ".gpkg", ".geojson")
    raster_exts = (".tif", ".img")

    candidates = []

    for root, _, files in os.walk(project_folder):
        for f in files:
            fname = f.lower()
            path = os.path.join(root, f)

            # --- Détection vecteur
            if fname.endswith(vector_exts):

                stem = os.path.splitext(fname)[0]

                file_tokens = stem.split("_")

                if file_tokens[-1] == expected_geom:
                    if all(t in file_tokens for t in expected_tokens):
                        print("Candidate vector:", fname)
                        candidates.append(path)
            
            # --- Détection raster
            elif fname.endswith(raster_exts):
                stem = os.path.splitext(fname)[0]
                file_tokens = stem.split("_")
                if all(t in file_tokens for t in expected_tokens):
                    print("Candidate raster:", fname)
                    candidates.append(path)

    if candidates:
        best = max(candidates, key=lambda p: len(os.path.splitext(os.path.basename(p))[0].split("_")))
        print(f"Best candidate: {best}")
        return best

    # ----------------------------
    # Vérification finale
    # ----------------------------
    for path in candidates:
        if path.lower().endswith(vector_exts):
            layer = QgsVectorLayer(path, "tmp", "ogr")
            if not layer.isValid():
                continue
            return path
        
    print(f"No valid layer found in candidates: {candidates}")


find_best_layer_qgis(project_folder, label)