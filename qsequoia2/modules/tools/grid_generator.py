from math import ceil, sqrt
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from qgis import processing
from qgis.core import (
    Qgis,
    QgsMapLayer,
    QgsProcessingException,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsFileWidget, QgsMapLayerComboBox

from qsequoia2.modules.utils.Qmessage import messageBar


class GridGenerator(QDialog):
    """
    Generate a regular sampling grid from a polygon layer.

    Sample size:
        n = (t * CV / ER)²

    CV and ER must use the same unit, normally percentages.
    """

    def __init__(
        self,
        iface,
        parent=None,
        *,
        student_factor: float = 2.0,
    ):
        super().__init__(parent or iface.mainWindow())

        self.iface = iface
        self.student_factor = student_factor
        self.required_points = 0

        self.setWindowTitle("Générer une grille de placettes")
        self.setMinimumWidth(520)

        self._build_ui()
        self._configure_ui()
        self._connect_signals()
        self._set_active_layer()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.layer_input = QgsMapLayerComboBox(self)

        self.cv_input = QDoubleSpinBox(self)
        self.er_input = QDoubleSpinBox(self)

        self.area_value = QLabel("—", self)
        self.student_value = QLabel(
            f"{self.student_factor:.3f}",
            self,
        )
        self.required_value = QLabel("—", self)

        self.points_ha_input = QDoubleSpinBox(self)
        self.spacing_value = QLabel("—", self)

        self.calculate_button = QPushButton(
            "Calculer le nombre de placettes",
            self,
        )

        self.output_input = QgsFileWidget(self)

        parameters_form = QFormLayout()
        parameters_form.addRow("Couche polygonale", self.layer_input)
        parameters_form.addRow("Coefficient de variation (CV)", self.cv_input)
        parameters_form.addRow("Erreur relative (ER)", self.er_input)
        parameters_form.addRow("Facteur de Student (t)", self.student_value)

        parameters_group = QGroupBox("Paramètres statistiques", self)
        parameters_group.setLayout(parameters_form)

        results_form = QFormLayout()
        results_form.addRow("Surface", self.area_value)
        results_form.addRow(
            "Nombre théorique de placettes",
            self.required_value,
        )
        results_form.addRow(
            "Densité de placettes",
            self.points_ha_input,
        )
        results_form.addRow("Espacement de la grille", self.spacing_value)

        results_group = QGroupBox("Résultat", self)
        results_group.setLayout(results_form)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel,
            parent=self,
        )

        self.generate_button = self.buttons.addButton(
            "Générer la grille",
            QDialogButtonBox.AcceptRole,
        )

        calculate_layout = QHBoxLayout()
        calculate_layout.addStretch()
        calculate_layout.addWidget(self.calculate_button)

        layout = QVBoxLayout(self)
        layout.addWidget(parameters_group)
        layout.addLayout(calculate_layout)
        layout.addWidget(results_group)
        layout.addWidget(QLabel("Sortie GeoPackage (facultative)", self))
        layout.addWidget(self.output_input)
        layout.addWidget(self.buttons)

    def _configure_ui(self):
        self.layer_input.setFilters(
            Qgis.LayerFilter.PolygonLayer
        )
        self.layer_input.setAllowEmptyLayer(True)
        self.layer_input.setShowCrs(True)

        self.cv_input.setRange(0.01, 1_000)
        self.cv_input.setDecimals(2)
        self.cv_input.setSuffix(" %")
        self.cv_input.setValue(30)
        self.cv_input.setKeyboardTracking(False)

        self.er_input.setRange(0.01, 100)
        self.er_input.setDecimals(2)
        self.er_input.setSuffix(" %")
        self.er_input.setValue(10)
        self.er_input.setKeyboardTracking(False)

        self.points_ha_input.setRange(0, 100_000)
        self.points_ha_input.setDecimals(4)
        self.points_ha_input.setSuffix(" point/ha")
        self.points_ha_input.setKeyboardTracking(False)

        self.output_input.setStorageMode(
            QgsFileWidget.SaveFile
        )
        self.output_input.setFilter(
            "GeoPackage (*.gpkg)"
        )
        self.output_input.setDialogTitle(
            "Enregistrer la grille de placettes"
        )
        self.output_input.setConfirmOverwrite(True)
        self.output_input.setUseLink(False)

        project_home = QgsProject.instance().homePath()
        if project_home:
            self.output_input.setDefaultRoot(project_home)

        self.generate_button.setEnabled(False)

    def _connect_signals(self):
        self.calculate_button.clicked.connect(
            self.calculate
        )
        self.buttons.accepted.connect(
            self.generate
        )
        self.buttons.rejected.connect(
            self.reject
        )

        self.layer_input.layerChanged.connect(
            self._invalidate_calculation
        )
        self.cv_input.valueChanged.connect(
            self._invalidate_calculation
        )
        self.er_input.valueChanged.connect(
            self._invalidate_calculation
        )

        self.points_ha_input.valueChanged.connect(
            self._update_spacing
        )

    def _set_active_layer(self):
        layer = self.iface.activeLayer()

        if (
            layer
            and layer.isValid()
            and layer.type() == Qgis.LayerType.Vector
            and layer.geometryType() == Qgis.GeometryType.Polygon
        ):
            self.layer_input.setLayer(layer)

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------

    def calculate(self):
        try:
            layer = self._input_layer()
            self._validate_crs(layer)

            area_ha = self._area_hectares(layer)
            cv = self.cv_input.value()
            er = self.er_input.value()

            self.required_points = self._sample_size(
                cv=cv,
                relative_error=er,
                student_factor=self.student_factor,
            )

            density = self.required_points / area_ha

        except ValueError as error:
            messageBar(
                self.iface,
                str(error),
                "w",
            )
            return

        self.area_value.setText(
            f"{area_ha:,.2f} ha".replace(",", " ")
        )
        self.required_value.setText(
            str(self.required_points)
        )

        # This remains editable after calculation.
        self.points_ha_input.setValue(density)

    @staticmethod
    def _sample_size(
        *,
        cv: float,
        relative_error: float,
        student_factor: float,
    ) -> int:
        if cv <= 0:
            raise ValueError(
                "Le coefficient de variation doit être positif."
            )

        if relative_error <= 0:
            raise ValueError(
                "L’erreur relative doit être positive."
            )

        if student_factor <= 0:
            raise ValueError(
                "Le facteur de Student doit être positif."
            )

        return ceil(
            (
                student_factor
                * cv
                / relative_error
            )
            ** 2
        )

    @staticmethod
    def _area_hectares(layer) -> float:
        area_m2 = sum(
            feature.geometry().area()
            for feature in layer.getFeatures()
            if feature.hasGeometry()
            and not feature.geometry().isEmpty()
        )

        area_ha = area_m2 / 10_000

        if area_ha <= 0:
            raise ValueError(
                "La couche sélectionnée ne contient aucune surface valide."
            )

        return area_ha

    @staticmethod
    def _spacing(points_per_ha: float) -> float:
        if points_per_ha <= 0:
            raise ValueError(
                "La densité de placettes doit être positive."
            )

        return sqrt(
            10_000 / points_per_ha
        )

    def _update_spacing(self, density: float):
        if density <= 0:
            self.spacing_value.setText("—")
            self.generate_button.setEnabled(False)
            return

        spacing = self._spacing(density)

        self.spacing_value.setText(
            f"{spacing:.2f} m"
        )
        self.generate_button.setEnabled(
            self.layer_input.currentLayer() is not None
        )

    def _invalidate_calculation(self, *_):
        self.required_points = 0

        self.area_value.setText("—")
        self.required_value.setText("—")
        self.points_ha_input.setValue(0)
        self.spacing_value.setText("—")
        self.generate_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def generate(self):
        try:
            layer = self._input_layer()
            self._validate_crs(layer)

            density = self.points_ha_input.value()
            spacing = self._spacing(density)
            output = self._output_destination()

            QApplication.setOverrideCursor(
                Qt.WaitCursor
            )

            grid = processing.run(
                "native:creategrid",
                {
                    "TYPE": 0,
                    "EXTENT": layer.extent(),
                    "HSPACING": spacing,
                    "VSPACING": spacing,
                    "HOVERLAY": 0,
                    "VOVERLAY": 0,
                    "CRS": layer.crs(),
                    "OUTPUT": "TEMPORARY_OUTPUT",
                },
            )["OUTPUT"]

            result = processing.run(
                "native:extractbylocation",
                {
                    "INPUT": grid,
                    "PREDICATE": [0],
                    "INTERSECT": layer,
                    "OUTPUT": output,
                },
            )

            output_layer = self._load_output_layer(
                result["OUTPUT"]
            )

        except (
            ValueError,
            QgsProcessingException,
            RuntimeError,
        ) as error:
            messageBar(
                self.iface,
                f"Impossible de générer la grille : {error}",
                "w",
            )
            return

        finally:
            QApplication.restoreOverrideCursor()

        generated_count = output_layer.featureCount()

        theoretical = (
            f" Objectif théorique : {self.required_points}."
            if self.required_points
            else ""
        )

        messageBar(
            self.iface,
            (
                f"{generated_count} placettes générées. "
                f"Sortie : {self._output_label()}."
                f"{theoretical}"
            ),
            "s",
        )

        self.accept()

    def _input_layer(self):
        layer = self.layer_input.currentLayer()

        if not layer or not layer.isValid():
            raise ValueError(
                "Sélectionnez une couche polygonale valide."
            )

        return layer

    @staticmethod
    def _validate_crs(layer):
        crs = layer.crs()

        if not crs.isValid():
            raise ValueError(
                "La couche ne possède pas de SCR valide."
            )

        if crs.mapUnits() != Qgis.DistanceUnit.Meters:
            raise ValueError(
                "La couche doit utiliser un SCR projeté en mètres."
            )

    def _output_destination(self):
        path = self.output_input.filePath().strip()

        if not path:
            return "TEMPORARY_OUTPUT"

        output = Path(path)

        if output.suffix.lower() != ".gpkg":
            output = output.with_suffix(".gpkg")

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        return str(output)

    def _load_output_layer(self, output):
        if isinstance(output, QgsMapLayer):
            layer = output
        else:
            output = str(output)

            layer = QgsVectorLayer(
                output,
                Path(output).stem,
                "ogr",
            )

        if not layer or not layer.isValid():
            raise RuntimeError(
                "La grille a été créée mais ne peut pas être chargée."
            )

        if QgsProject.instance().mapLayer(layer.id()) is None:
            QgsProject.instance().addMapLayer(layer)

        return layer

    def _output_label(self):
        path = self.output_input.filePath().strip()

        if not path:
            return "couche temporaire"

        output = Path(path)

        if output.suffix.lower() != ".gpkg":
            output = output.with_suffix(".gpkg")

        return str(output)