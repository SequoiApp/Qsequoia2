

import os,json

from ..utils.add_vector_layers import load_vectors
from ..utils.add_raster_layers import load_rasters
from ..utils.add_wmts_layers import load_wmts

from ..utils.layers import *
from ..utils.config import *
from ..utils.messageBar import *
from .layout_loader import LayoutLoader


class LayoutBuilder:

    def __init__(self, iface, config, project_key: str):
        
        self.parent = None
        self.project = QgsProject.instance()

        self.iface = iface
        self.config = config
        self.project_key = project_key

        self.canvas = self.config.get_canvas(project_key)
        self.layout = self.config.get_layout(project_key)

    def load_layer_and_groups(self):
        """
        Charge les couches vectorielles, raster et WMTS dans les groupes définis
        dans le YAML du projet.

        - Les groupes sont créés si inexistants.
        - Les couches déjà chargées ne sont pas doublées.
        - Les WMTS sont chargés en une seule fois par groupe.
        """

        loaders = {
            "vector": load_vectors,
            "wmts": load_wmts,
            "raster": load_rasters}

        project = QgsProject.instance()
        root = project.layerTreeRoot()

        # Groupe racine
        root_group = root.findGroup(self.project_key) or root.addGroup(self.project_key)


        for group in self.canvas_cfg.groups:

            gtype = group.get("type")
            layers = group.get("layers") or []
            canvas_group_name = group.get("name", "Sans nom")
            subgroup = root_group.findGroup(canvas_group_name) or root_group.addGroup(canvas_group_name)

            loader = loaders.get(gtype)

            messageLog(f"Groupe chargé : {gtype}", "w")
            if not loader:
                messageLog(f"Groupe inconnu : {gtype}", "w")
                continue

            # ======================================================
            # WMTS : appeler une seule fois avec la liste
            # ======================================================
            if gtype == "wmts":
                loader(layers, group_name=canvas_group_name)
                continue

            # ======================================================
            # VECTOR
            # ======================================================

            if gtype == "vector":

                for layer_name in layers:

                    layer_paths_dict = get_path(layer_name,project_name=self.project_name,
                                                project_folder=self.project_folder,
                                                style_folder=self.style_folder,
                                                parent=self,
                                                layout_mode=1)

                    if not layer_paths_dict:
                        messageLog(f"Layer NOT found: {layer_name}","w")
                        continue

                    layer_name_key = list(layer_paths_dict.keys())[0]
                    source_path = layer_paths_dict[layer_name_key]
                    final_path = source_path

                    # --------------------------------------------------
                    #  Vérifier si déjà chargé
                    # --------------------------------------------------

                    existing_layer = None
                    for l in self.project.mapLayers().values():
                        if l.source() == final_path:
                            existing_layer = l
                            break

                    if existing_layer:
                        node = root.findLayer(existing_layer.id())
                        if node and node.parent() != subgroup:
                            subgroup.addLayer(existing_layer)
                        continue


                    # --------------------------------------------------
                    #  Charger les couches sur QGIS
                    # --------------------------------------------------

                    loader(
                        {layer_name_key: final_path},
                        style_folder=self.style_folder,
                        project_folder=self.project_folder,
                        project_name=self.project_name,
                        group_name=canvas_group_name,
                        parent_group=subgroup,
                        parent=self)


    def fold_all(self):
        """
        Plie tous les groupes de l'arborescence de couches du projet.
        """

        root = self.project.layerTreeRoot()
        for node in root.children():
            node.setExpanded(False)

    def unfold(self, group_name):
        """
        Déplie un groupe spécifique dans l'arborescence de couches du projet.

        Args:
            group_name (str): Nom du groupe à déplier.
        """

        root = self.project.layerTreeRoot()
        group = root.findGroup(group_name)

        if group:
            group.setExpanded(True)

    def zoom_on_layer(self, key):
        """
        Zoome sur l'étendue de la couche spécifiée dans le canvas QGIS.

        Args:
            key (str): Clé de la couche à zoomer.
        """
        layer = resolve_layer(key,
                              project=self.project,
                              project_name=self.project_name,
                              project_folder=self.project_folder,
                              style_folder=self.style_folder,
                              parent=self)
        if not layer:
            return
        canvas = self.iface.mapCanvas()
        canvas.setExtent(layer.extent())
        canvas.refresh()

    def apply_scan25_opacity(self):
        """
        Applique une opacité de 50% à la couche WMTS 'scan25_grey' si elle existe.
        """

        layer_name = get_wmts("wmts_scan25_grey")[0]
        layers = self.project.mapLayersByName(layer_name)

        if layers:
            layers[0].setOpacity(0.5)

    def build(self):
        """
        Méthode principale pour construire la mise en page du projet.

        Actions effectuées :
        1. Chargement des couches dans les groupes.
        2. Création de tous les thèmes.
        3. Pliage et dépliage de l'arborescence.
        4. Zoom sur la couche définie dans le YAML.
        5. Application de l'opacité sur la couche WMTS spécifique.
        6. Message de succès dans la barre d'état.
        """

        messageBar(self.iface, f"Création de la mise en page : {self.project_key}", "i",8)

        self.load_layer_and_groups() # Chargement des couches dans les groupes
        self.create_all_themes() # Chargement des 

        self.fold_all()
        self.unfold(self.project_key)

        self.zoom_on_layer(self.canvas_cfg.zoom_on)
        self.apply_scan25_opacity()

        messageBar(self.iface, f"Mise en page {self.project_key} chargé avec succès", "s",8)















