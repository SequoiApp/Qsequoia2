from pathlib import Path
import sqlite3

from qgis.core import (
    QgsEditorWidgetSetup, QgsExpression, QgsFeatureRequest, QgsProject,
    QgsProviderRegistry, QgsVariantUtils, QgsVectorLayer, QgsVectorLayerUtils,
)
from qgis.gui import QgsAttributeDialog, QgsAttributeEditorContext
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QMessageBox, QWidget

from ..utils.Qmessage import messageBar, messageLog
from ..utils.seq_config import resolve_seq_layer, seq_field, seq_layer
from ..utils.variable import get_project_variable
from . import database

UI_PATH = Path(__file__).parent / "engagement_fiscaux.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))

IDU_FIELD = seq_field("idu")["name"]

def populate_combo(combo, items, selected=None):
    combo.clear()
    for fid, name, kind in items:
        combo.addItem(f"{name} ({kind})", fid)
    combo.setCurrentIndex(max(0, combo.findData(selected)))
    has_items = bool(items)
    combo.setEnabled(has_items)


class EngagementFiscauxDialog(QWidget, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.project = QgsProject.instance()
        self.setupUi(self)

        self.parca = None
        self.seq_id = get_project_variable("QS2_seq_id")
        self.table = f"{self.seq_id}_{seq_layer('parca')['name']}"

        self.btn_create_tables.clicked.connect(self.create_or_import_tables)
        self.btn_add_engagement.clicked.connect(self.add_engagement)
        self.btn_edit.clicked.connect(self.edit_engagement)

        self.btn_link_parcels.clicked.connect(self.link_parcels)
        self.btn_unlink_parcels.clicked.connect(self.unlink_parcels)
        self.btn_delete.clicked.connect(self.delete_engagement)

        self.cb_engagements.activated.connect(self.show_engagement)
        self.cb_target.currentIndexChanged.connect(self.on_selection_changed)

        self.project.layersAdded.connect(self.refresh)
        self.project.layersRemoved.connect(self.refresh)

        self.refresh()

    def refresh(self):
        parca = resolve_seq_layer("parca", self.project, seq_id=self.seq_id, spatial_only=True)
        parca_is_loaded = parca is not None

        # Connect parca selectionChanged signal only once
        parca_has_changed = parca is not self.parca
        if parca_is_loaded and parca_has_changed:
            parca.selectionChanged.connect(self.on_selection_changed)

        self.parca = parca


        # Find database path
        self.path = None
        if parca_is_loaded:
            source = QgsProviderRegistry.instance().decodeUri("ogr", self.parca.source())
            self.path = Path(self.project.readPath(source["path"])).resolve()

        # Update UI state
        engagements = database.engagements(self.path) if parca_is_loaded else None
        has_tables = engagements is not None
        has_engagements = bool(engagements)

        self.btn_create_tables.setEnabled(parca_is_loaded)
        self.btn_create_tables.setText("Importer les tables" if has_tables else "Créer les tables")
        self.btn_create_tables.setToolTip(
            "Charger les tables dans le projet en lecture seule." if has_tables else ""
        )
        self.btn_add_engagement.setEnabled(has_tables)

        for combo in (self.cb_engagements, self.cb_target):
            populate_combo(combo, engagements or [], combo.currentData())

        # Set widget editability
        self.lbl_status.setVisible(not parca_is_loaded)
        self.grp_selection.setEnabled(has_engagements)
        self.grp_assignment.setEnabled(has_engagements)

    def on_selection_changed(self):
        # Update parcels assignement UI
        parca_is_loaded = self.parca is not None
        count = self.parca.selectedFeatureCount() if parca_is_loaded else 0
        self.grp_assignment.setTitle(f"Sélection PARCA ({count})")

        has_selected_parcels = count > 0
        has_target_engagement = self.cb_target.currentData() is not None
        self.btn_link_parcels.setEnabled(has_selected_parcels and has_target_engagement)
        self.btn_unlink_parcels.setEnabled(has_selected_parcels and has_target_engagement)

        # Update engagement edition UI
        has_selected_engagement = self.cb_engagements.currentData() is not None
        self.btn_edit.setEnabled(has_selected_engagement)
        self.btn_delete.setEnabled(has_selected_engagement)

    def create_or_import_tables(self):
        try:
            has_tables = database.engagements(self.path) is not None
            if has_tables:
                self.import_tables()
                return
            created = database.create_tables(self.path, self.table)
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        self.refresh()

        if created:
            messageBar(self.iface, "Les tables d’engagements fiscaux sont prêtes.", "s")
        else:
            messageBar(self.iface, "Les tables d’engagements fiscaux existent déjà.", "i")

    def table_layer(self, table):
        uri = QgsProviderRegistry.instance().encodeUri("ogr", {"path": str(self.path), "layerName": table})
        return QgsVectorLayer(uri, table, "ogr")

    def import_tables(self):
        for table in (database.ENGAGEMENTS_TABLE_NAME, database.PARCA_ENGAGEMENTS_TABLE_NAME):
            layer = self.table_layer(table)
            existing = next((item for item in self.project.mapLayers().values()
                             if isinstance(item, QgsVectorLayer) and item.source() == layer.source()), None)
            if existing is not None:
                layer = existing
            layer_is_valid = layer.isValid()
            if not layer_is_valid:
                messageBar(self.iface, f"Impossible d’ouvrir la table {table}.", "c")
                return
            is_read_only = layer.setReadOnly(True)
            if not is_read_only:
                messageBar(self.iface, f"Terminez l’édition de {table} avant de l’importer en lecture seule.", "w")
                return
            if existing is None:
                self.project.addMapLayer(layer)
        self.refresh()

    def edit_engagement(self):
        fid = self.cb_engagements.currentData()
        if fid is None:
            return

        layer = self.table_layer(database.ENGAGEMENTS_TABLE_NAME)
        if not layer.isValid():
            messageBar(self.iface, "Impossible d’ouvrir la table des engagements.", "c")
            return

        feature = layer.getFeature(fid)
        if not feature.isValid():
            messageBar(self.iface, "Engagement introuvable.", "c")
            self.refresh()
            return

        if not layer.startEditing():
            messageBar(self.iface, "Impossible de modifier la table des engagements.", "c")
            return

        self.configure_engagement_fields(layer)
        form = QgsAttributeDialog(layer, feature, False, self)
        form.setWindowTitle("Modifier un engagement fiscal")
        form.setMode(QgsAttributeEditorContext.SingleEditMode)
        if not form.exec():
            layer.rollBack()
            return

        if not layer.commitChanges():
            messageBar(self.iface, "\n".join(layer.commitErrors()), "c")
            layer.rollBack()
            return

        self.refresh()

    def add_engagement(self):
        layer = self.table_layer(database.ENGAGEMENTS_TABLE_NAME)
        if not layer.startEditing():
            messageBar(self.iface, "Impossible de modifier la table des engagements.", "c")
            return

        self.configure_engagement_fields(layer)
        feature = QgsVectorLayerUtils.createFeature(layer)
        form = QgsAttributeDialog(layer, feature, False, self)
        form.setWindowTitle("Ajouter un engagement fiscal")
        form.setMode(QgsAttributeEditorContext.AddFeatureMode)
        if not form.exec():
            layer.rollBack()
            return

        if not layer.commitChanges():
            messageBar(self.iface, "\n".join(layer.commitErrors()), "c")
            layer.rollBack()
            return

        self.refresh()

    @staticmethod
    def configure_engagement_fields(layer):
        type_index = layer.fields().indexFromName("TYPE")
        if type_index != -1:
            layer.setEditorWidgetSetup(
                type_index,
                QgsEditorWidgetSetup(
                    "ValueMap", {"map": [{"IFI": "IFI"}, {"MONICHON": "MONICHON"}]}
                ))

        fid_index = layer.fields().indexFromName("fid")
        if fid_index != -1:
            layer.setEditorWidgetSetup(
                fid_index,
                QgsEditorWidgetSetup("Hidden", {})
            )

            config = layer.editFormConfig()
            config.setReadOnly(fid_index, True)
            layer.setEditFormConfig(config)

    def link_parcels(self):
        fid = self.cb_target.currentData()
        idus = [feature[IDU_FIELD] for feature in self.parca.getSelectedFeatures()]
        try:
            # Convert QGIS NULL to SQL NULL so SQLite checks the constraint.
            idus = [None if QgsVariantUtils.isNull(idu) else idu for idu in idus]
            added = database.link_parcels(self.path, fid, idus)
            result = f"ajoutées : {added}, déjà associées : {len(idus) - added}"
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        self.show_engagement()
        messageBar(self.iface, f"{self.cb_target.currentText()} — {result}.", "s")

    def unlink_parcels(self):
        fid = self.cb_target.currentData()
        idus = [feature[IDU_FIELD] for feature in self.parca.getSelectedFeatures()]
        try:
            # Convert QGIS NULL to SQL NULL so SQLite checks the constraint.
            idus = [None if QgsVariantUtils.isNull(idu) else idu for idu in idus]
            removed = database.unlink_parcels(self.path, fid, idus)
            result = f"parcelles dissociées : {removed}"
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        self.show_engagement()
        messageBar(self.iface, f"{self.cb_target.currentText()} — {result}.", "s")

    def parcel_summary(self, fid):
        """Return the total count, area in hectares and selectable QGIS feature IDs."""
        idus = database.parcel_ids(self.path, fid)
        if not idus:
            return 0, 0.0, set()

        values = ", ".join(QgsExpression.quotedString(idu) for idu in idus)
        request = QgsFeatureRequest().setFilterExpression(f'"{IDU_FIELD}" IN ({values})')

        # Totals include every linked parcel, even when the map is filtered.
        parcels = (
            self.table_layer(self.table)
            if self.parca.subsetString()
            else self.parca
        )

        hectares = 0.0
        complete = True
        ids = set()
        for feature in parcels.getFeatures(request):
            ids.add(feature.id())
            area = feature[seq_field("cad_area")["name"]]
            if QgsVariantUtils.isNull(area):
                complete = False
            else:
                hectares += float(area)

        count = len(ids)
        if self.parca.subsetString():
            ids = {feature.id() for feature in self.parca.getFeatures(request)}

        return count, hectares if complete else None, ids

    def show_engagement(self):
        fid = self.cb_engagements.currentData()
        self.engaged_ids = set()
        self.on_selection_changed()
        if fid is not None:
            count, hectares, self.engaged_ids = self.parcel_summary(fid)
            self.lbl_parcel_count.setText(str(count))
            self.lbl_area_value.setText("Indisponible" if hectares is None else f"{hectares:.2f} ha")
        else:
            self.lbl_parcel_count.setText("-")
            self.lbl_area_value.setText("-")
            
        if self.parca:
            self.parca.selectByIds(list(self.engaged_ids))

    def delete_engagement(self):
        fid = self.cb_engagements.currentData()
        name = self.cb_engagements.currentText()
        path = self.path
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self, "Supprimer l’engagement",
                                      f"Supprimer {name} et ses associations aux parcelles ?",
                                      buttons.Yes | buttons.No, buttons.No)
        if answer != buttons.Yes:
            return
        try:
            database.delete_engagement(path, fid)
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        if self.parca and set(self.parca.selectedFeatureIds()) == self.engaged_ids:
            self.parca.removeSelection()
        self.refresh()
        messageBar(self.iface, f"Engagement {name} supprimé.", "s")
