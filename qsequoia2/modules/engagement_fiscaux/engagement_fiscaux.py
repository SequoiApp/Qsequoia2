from pathlib import Path
import sqlite3

from qgis.core import (
    QgsApplication, QgsExpression, QgsFeatureRequest, QgsProject,
    QgsVariantUtils, QgsVectorLayerUtils,
)
from qgis.gui import QgsAttributeDialog, QgsAttributeEditorContext
from qgis.PyQt import uic
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import QMessageBox, QWidget

from qsequoia2.modules.database.database_manager import Qsequoia2DbManager
from qsequoia2.modules.database.database_entities import Qsequoia2DbEntities
from qsequoia2.modules.utils.Qmessage import messageBar
from qsequoia2.modules.utils.seq_config import resolve_seq_layer, seq_field, seq_read
from qsequoia2.modules.utils.variable import get_project_variable

FORM_CLASS, _ = uic.loadUiType(str(Path(__file__).parent / "engagement_fiscaux.ui"))

IDU_FIELD = seq_field("idu")["name"]
GPKG_KEY = "v.seq.parca.poly"
ENGAGEMENTS = "ENGAGEMENTS_FISCAUX"
LINKS = "PARCA_POSSEDE_ENGAGEMENTS"


def populate_combo(combo, items, selected=None):
    combo.clear()
    for fid, name, kind in items:
        combo.addItem(f"{name} ({kind})", fid)
    combo.setCurrentIndex(max(0, combo.findData(selected)))
    combo.setEnabled(bool(items))


class EngagementFiscauxDialog(QWidget, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.project = QgsProject.instance()
        self.parca_layer = self.engagement_layer = self.dbm = self.dbe = self.seq_dir = None
        self.engaged_ids = set()

        icon = QgsApplication.getThemeIcon
        self.btn_refresh.setIcon(icon("/mActionRefresh.svg"))
        self.btn_add.setIcon(icon("/mActionAdd.svg"))
        self.btn_edit.setIcon(icon("/mActionToggleEditing.svg"))
        self.btn_delete.setIcon(icon("/mActionRemove.svg"))

        self.btn_refresh.clicked.connect(self.on_parca_layer_loaded)
        self.btn_add.clicked.connect(self.add_engagement)
        self.btn_edit.clicked.connect(self.edit_engagement)
        self.btn_delete.clicked.connect(self.delete_engagement)
        self.btn_link_parcels.clicked.connect(self.link_parcels)
        self.btn_unlink_parcels.clicked.connect(self.unlink_parcels)
        self.cb_engagements.activated.connect(self.show_engagement)
        self.project.layersAdded.connect(self._on_layers_changed)
        self.project.layersRemoved.connect(self._on_layers_changed)

        self.on_parca_layer_loaded()

    def _on_layers_changed(self, *args):
        QTimer.singleShot(0, self.on_parca_layer_loaded)

    def on_parca_layer_loaded(self, *args):
        try:
            self.parca_layer.selectionChanged.disconnect(self.on_selection_changed)
        except (AttributeError, TypeError, RuntimeError):
            pass
        if self.dbm is not None:
            self.dbm.close()

        self.parca_layer = resolve_seq_layer("parca", self.project, seq_id=get_project_variable("QS2_seq_id"), spatial_only=True)
        self.seq_dir = get_project_variable("QS2_seq_dir")
        loaded = self.parca_layer is not None and self.seq_dir is not None

        self.lbl_parca_status.setText("Couche PARCA chargée" if loaded else "Couche PARCA non chargée")
        self.lbl_parca_status.setStyleSheet(f"color: {'green' if loaded else 'red'};")
        self.btn_add.setEnabled(loaded)

        if not loaded:
            self.parca_layer = self.engagement_layer = self.dbm = self.dbe = None
        else:
            self.parca_layer.selectionChanged.connect(self.on_selection_changed)
            self.dbm = Qsequoia2DbManager(GPKG_KEY)
            self.dbe = Qsequoia2DbEntities(self.dbm)
            self.engagement_layer = self._engagement_layer(create=False)
        self.refresh()

    def _engagement_layer(self, create=False):
        """Couche ENGAGEMENTS_FISCAUX (ajoutée au projet si besoin). Crée les tables si create=True."""
        if not self.dbe.get_columns(ENGAGEMENTS):
            if not create:
                return None
            if not self.dbm.ddl_execute("tax_commitments"):
                messageBar(self.iface, "Échec de création des tables d’engagements fiscaux.", "c")
                return None
        try:
            return seq_read(GPKG_KEY, self.seq_dir, add_to_project=True,
                            layername=ENGAGEMENTS, if_exists="return")
        except RuntimeError as error:
            messageBar(self.iface, str(error), "c")
            return None

    def refresh(self, *args):
        items = {}
        if self.engagement_layer:
            for f in self.engagement_layer.getFeatures():
                items.setdefault(f["NOM"], (f.id(), f["NOM"], f["TYPE"]))
        populate_combo(self.cb_engagements, list(items.values()), self.cb_engagements.currentData())
        self.on_selection_changed()

    def on_selection_changed(self, *args):
        has_engagement = self.cb_engagements.currentData() is not None
        has_parcels = bool(self.parca_layer and self.parca_layer.selectedFeatureCount())
        self.btn_edit.setEnabled(has_engagement)
        self.btn_delete.setEnabled(has_engagement)
        self.btn_link_parcels.setEnabled(has_engagement and has_parcels)
        self.btn_unlink_parcels.setEnabled(has_engagement and has_parcels)

    def show_engagement(self, *args):
        fid = self.cb_engagements.currentData()
        count, hectares, self.engaged_ids = self.parcel_summary(fid) if fid is not None else ("-", None, set())
        self.lbl_parcel_count.setText(str(count))
        self.lbl_area_value.setText("-" if fid is None else "Indisponible" if hectares is None else f"{hectares:.2f} ha")
        if self.parca_layer:
            self.parca_layer.removeSelection()
            self.parca_layer.selectByIds(list(self.engaged_ids))
            self.iface.mapCanvas().zoomToSelected(self.parca_layer)
            self.iface.mapCanvas().refresh()

        self.on_selection_changed()

    def parcel_summary(self, fid):
        """Nombre de parcelles, surface (ha, None si incomplète) et fid QGIS des parcelles liées."""
        rows = self.dbe.request(LINKS, "ENGAGEMENT_FID", fid, fetchone=False) or []
        if not rows:
            return 0, 0.0, set()

        values = ", ".join(QgsExpression.quotedString(r["IDU"]) for r in rows)
        request = QgsFeatureRequest().setFilterExpression(f'"{IDU_FIELD}" IN ({values})')
        area_field = seq_field("cad_area")["name"]

        ids, areas = set(), []
        for f in self.parca_layer.getFeatures(request):
            ids.add(f.id())
            areas.append(None if QgsVariantUtils.isNull(f[area_field]) else float(f[area_field]))
        return len(ids), (None if None in areas else sum(areas)), ids

    def _edit_form(self, feature, title, mode):
        layer = self.engagement_layer
        if not layer.startEditing():
            messageBar(self.iface, "Impossible de modifier la table des engagements.", "c")
            return
        form = QgsAttributeDialog(layer, feature, False, self)
        form.setWindowTitle(title)
        form.setMode(mode)
        if not form.exec():
            layer.rollBack()
            return
        if not layer.commitChanges():
            messageBar(self.iface, "\n".join(layer.commitErrors()), "c")
            layer.rollBack()
            return
        self.refresh()

    def add_engagement(self):
        self.engagement_layer = self._engagement_layer(create=True)
        if self.engagement_layer:
            self._edit_form(QgsVectorLayerUtils.createFeature(self.engagement_layer),
                            "Ajouter un engagement fiscal", QgsAttributeEditorContext.AddFeatureMode)

    def edit_engagement(self):
        self._edit_form(self.engagement_layer.getFeature(self.cb_engagements.currentData()),
                        "Modifier un engagement fiscal", QgsAttributeEditorContext.SingleEditMode)

    def delete_engagement(self):
        fid, name = self.cb_engagements.currentData(), self.cb_engagements.currentText()
        buttons = QMessageBox.StandardButton
        if QMessageBox.question(self, "Supprimer l’engagement",
                                f"Supprimer {name} et ses associations aux parcelles ?",
                                buttons.Yes | buttons.No, buttons.No) != buttons.Yes:
            return
        try:
            self.dbe.delete_cascade(ENGAGEMENTS, "fid", [fid])
        except sqlite3.Error as error:
            messageBar(self.iface, str(error), "c")
            return

        if self.parca_layer and set(self.parca_layer.selectedFeatureIds()) == self.engaged_ids:
            self.parca_layer.removeSelection()
        self.engagement_layer.reload()
        self.refresh()
        messageBar(self.iface, f"Engagement {name} supprimé.", "s")

    def _selected_idus(self):
        return [f[IDU_FIELD] for f in self.parca_layer.getSelectedFeatures()
                if not QgsVariantUtils.isNull(f[IDU_FIELD])]

    def link_parcels(self):
        fid, idus, added = self.cb_engagements.currentData(), self._selected_idus(), 0
        for idu in idus:
            try:
                self.dbe.insert(LINKS, ("IDU", "ENGAGEMENT_FID"), (idu, fid))
                added += 1
            except sqlite3.IntegrityError:
                pass  # couple déjà présent (UNIQUE)
        self._report(f"ajoutées : {added}, déjà associées : {len(idus) - added}")

    def unlink_parcels(self):
        fid = self.cb_engagements.currentData()
        removed = sum(self.dbe.delete(LINKS, ("IDU", "ENGAGEMENT_FID"), (idu, fid))
                      for idu in self._selected_idus())
        self._report(f"parcelles dissociées : {removed}")

    def _report(self, result):
        self.show_engagement()
        messageBar(self.iface, f"{self.cb_engagements.currentText()} — {result}.", "s")
