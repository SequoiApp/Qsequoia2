from pathlib import Path
import sqlite3

from osgeo import gdal
from qgis.core import (
    QgsDistanceArea, QgsEditorWidgetSetup, QgsExpression, QgsFeatureRequest, QgsProject,
    QgsProviderRegistry, QgsUnitTypes, QgsVariantUtils, QgsVectorLayer, QgsVectorLayerUtils,
)
from qgis.gui import QgsAttributeDialog, QgsAttributeEditorContext
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QMessageBox, QWidget

from ..utils.Qmessage import messageBar
from ..utils.seq_config import resolve_seq_layer
from ..utils.variable import get_project_variable
from . import database

UI_PATH = Path(__file__).parent / "engagement_fiscaux.ui"
FORM_CLASS, _ = uic.loadUiType(str(UI_PATH))


def populate_combo(combo, rows, selected):
    combo.clear()
    combo.addItem("Choisir une certification…", None)
    for code, kind in rows:
        combo.addItem(f"{code} ({kind})", code)
    combo.setCurrentIndex(max(0, combo.findData(selected)))
    combo.setEnabled(bool(rows))


class EngagementFiscauxDialog(QWidget, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.project = QgsProject.instance()
        self.setupUi(self)

        self.parca = None
        self.set_layer(None)

        self.btn_create_tables.clicked.connect(self.create_tables)
        self.btn_add_engagement.clicked.connect(self.add_engagement)

        self.btn_link_parcels.clicked.connect(lambda: self.update_parcel_links(remove=False))
        self.btn_unlink_parcels.clicked.connect(lambda: self.update_parcel_links(remove=True))
        self.btn_delete.clicked.connect(self.delete_certification)

        self.cb_certifications.activated.connect(lambda _: self.show_certification(select=True))
        self.cb_target.currentIndexChanged.connect(self.update_actions)

        self.project.layersAdded.connect(self.refresh)
        self.project.layersWillBeRemoved.connect(self.layers_removing)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def layers_removing(self, layer_ids):
        if self.parca and self.parca.id() in layer_ids:
            self.set_layer(None)

    def set_layer(self, layer):
        if self.parca:
            self.parca.selectionChanged.disconnect(self.update_actions)
        self.parca = layer
        self.path = None
        self.lbl_status.setVisible(layer is None)
        self.btn_create_tables.setEnabled(layer is not None)
        if layer:
            layer.selectionChanged.connect(self.update_actions)
            source = QgsProviderRegistry.instance().decodeUri("ogr", layer.source())
            self.path = Path(self.project.readPath(source["path"])).resolve()
            self.table = source.get("layerName")
            if not self.table:
                dataset = gdal.OpenEx(str(self.path), gdal.OF_VECTOR)
                self.table = dataset.GetLayerByIndex(int(source.get("layerId") or 0)).GetName()
        self.cb_certifications.clear()
        self.cb_target.clear()
        self.refresh_choices()

    def refresh(self):
        layer = resolve_seq_layer("parca", self.project, seq_id=get_project_variable("QS2_seq_id"), spatial_only=True)
        if layer != self.parca:
            self.set_layer(layer)
        else:
            self.refresh_choices()

    def refresh_choices(self, target=None):
        rows = database.certifications(self.path) if self.path else None
        self.btn_add_engagement.setEnabled(rows is not None)
        populate_combo(self.cb_certifications, rows or [], self.cb_certifications.currentData())
        populate_combo(self.cb_target, rows or [], target or self.cb_target.currentData())
        self.show_certification()

    def update_actions(self):
        count = self.parca.selectedFeatureCount() if self.parca else 0
        self.grp_assignment.setTitle(f"Sélection PARCA ({count})")
        enabled = bool(count and self.cb_target.currentData())
        self.btn_link_parcels.setEnabled(enabled)
        self.btn_unlink_parcels.setEnabled(enabled)
        self.btn_delete.setEnabled(bool(self.cb_certifications.currentData()))

    def create_tables(self):
        try:
            created = database.create_tables(self.path, self.table)
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        self.refresh_choices()
        if created:
            messageBar(self.iface, "Les tables d’engagements fiscaux sont prêtes.", "s")
        else:
            messageBar(self.iface, "Les tables d’engagements fiscaux existent déjà.", "i")

    def table_layer(self, table, title):
        uri = QgsProviderRegistry.instance().encodeUri("ogr", {"path": str(self.path), "layerName": table})
        return QgsVectorLayer(uri, title, "ogr")

    def add_engagement(self):
        layer = self.table_layer("engagements_fiscaux", "Ajouter une certification")
        if not layer.startEditing():
            messageBar(self.iface, "Impossible de modifier la table des engagements.", "c")
            return
        layer.setEditorWidgetSetup(layer.fields().indexFromName("type"), QgsEditorWidgetSetup(
            "ValueMap", {"map": [{"IFI": "IFI"}, {"MONICHON": "MONICHON"}]}
        ))
        feature = QgsVectorLayerUtils.createFeature(layer)
        form = QgsAttributeDialog(layer, feature, False, self)
        form.setMode(QgsAttributeEditorContext.AddFeatureMode)
        if not form.exec():
            return
        code = form.feature()["engagement_id"]
        if not layer.commitChanges():
            messageBar(self.iface, "\n".join(layer.commitErrors()), "c")
            return
        self.refresh_choices(target=code)

    def update_parcel_links(self, remove):
        code = self.cb_target.currentData()
        idus = [feature["IDU"] for feature in self.parca.getSelectedFeatures()]
        try:
            # Convert QGIS NULL to SQL NULL so SQLite checks the constraint.
            idus = [None if QgsVariantUtils.isNull(idu) else idu for idu in idus]
            if remove:
                removed = database.unlink_parcels(self.path, code, idus)
                result = f"parcelles dissociées : {removed}"
            else:
                added = database.link_parcels(self.path, code, idus)
                result = f"ajoutées : {added}, déjà associées : {len(idus) - added}"
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        self.show_certification()
        messageBar(self.iface, f"{code} — {result}.", "s")

    def parcel_summary(self, code):
        """Return the total count, area in hectares and selectable QGIS feature IDs."""
        idus = database.parcel_ids(self.path, code)
        if not idus:
            return 0, 0.0, set()

        values = ", ".join(QgsExpression.quotedString(idu) for idu in idus)
        request = QgsFeatureRequest().setFilterExpression(f'"IDU" IN ({values})')
        # A map filter limits selection, but the totals include every linked parcel.
        parcels = self.table_layer(self.table, self.table) if self.parca.subsetString() else self.parca

        measure = QgsDistanceArea()
        measure.setSourceCrs(parcels.crs(), self.project.transformContext())
        ellipsoid = self.project.ellipsoid()
        measure.setEllipsoid("WGS84" if ellipsoid == "NONE" else ellipsoid)
        area_field = parcels.fields().lookupField("SURF_SIG")
        hectares = 0.0
        complete = True
        ids = set()
        for feature in parcels.getFeatures(request):
            ids.add(feature.id())
            if area_field >= 0 and not QgsVariantUtils.isNull(feature[area_field]):
                hectares += float(feature[area_field])
            elif feature.hasGeometry() and parcels.crs().isValid():
                area = measure.measureArea(feature.geometry())
                hectares += measure.convertAreaMeasurement(area, QgsUnitTypes.AreaHectares)
            else:
                complete = False

        count = len(ids)
        if self.parca.subsetString():
            ids = {feature.id() for feature in self.parca.getFeatures(request)}
        return count, hectares if complete else None, ids

    def show_certification(self, select=False):
        code = self.cb_certifications.currentData()
        self.certified_ids = set()
        self.update_actions()
        if code:
            count, hectares, self.certified_ids = self.parcel_summary(code)
            self.lbl_parcel_count.setText(str(count))
            self.lbl_area_value.setText("Indisponible" if hectares is None else f"{hectares:.2f} ha")
        else:
            self.lbl_parcel_count.setText("-")
            self.lbl_area_value.setText("-")
        if select and self.parca:
            self.parca.selectByIds(list(self.certified_ids))

    def delete_certification(self):
        code = self.cb_certifications.currentData()
        path = self.path
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(self, "Supprimer la certification",
                                      f"Supprimer « {code} » et ses associations aux parcelles ?",
                                      buttons.Yes | buttons.No, buttons.No)
        if answer != buttons.Yes:
            return
        try:
            database.delete_certification(path, code)
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return
        if self.parca and set(self.parca.selectedFeatureIds()) == self.certified_ids:
            self.parca.removeSelection()
        self.refresh_choices()
        messageBar(self.iface, f"Certification « {code} » supprimée.", "s")
