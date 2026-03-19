from __future__ import annotations

from pathlib import Path
from traceback import format_exc

from PyQt5.QtCore import QObject, QRunnable, QSettings, QThreadPool, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .branding import APP_NAME, cached_icon_path, current_icon_path, fetch_and_cache_icon
from .catalog import build_model_families
from .dae_bridge import build_render_scene, scan_rendinst_models, validate_game_root
from .i18n import detect_client_language, tr
from .model_table import ModelFilterProxy, ModelTableModel
from .types import ModelFamily, ModelIndexEntry, ModelVariant, RenderScene
from .viewer import ModelViewport

LIGHT_CUSTOM_KEY = "custom"
LIGHT_PRESETS: dict[str, dict[str, int]] = {
    "balanced": {"azimuth": 69, "elevation": 30, "brightness": 125},
    "studio": {"azimuth": 112, "elevation": 42, "brightness": 145},
    "overcast": {"azimuth": 18, "elevation": 72, "brightness": 105},
    "side": {"azimuth": 145, "elevation": 28, "brightness": 150},
}


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)


class FunctionWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            self.signals.failed.emit(format_exc())
            return
        self.signals.finished.emit(result)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.resize(1560, 920)

        self._thread_pool = QThreadPool()
        self._thread_pool.setMaxThreadCount(1)
        self._aux_thread_pool = QThreadPool()
        self._aux_thread_pool.setMaxThreadCount(1)
        self._settings = QSettings(APP_NAME, APP_NAME)

        self._model_items: list[ModelIndexEntry] = []
        self._model_families: list[ModelFamily] = []
        self._game_root: Path | None = None
        self._detected_locale = "en"
        self._loaded_variant: ModelVariant | None = None
        self._loaded_scene: RenderScene | None = None
        self._scan_generation = 0
        self._load_request_id = 0
        self._is_scanning = False
        self._is_loading = False

        self._table_model = ModelTableModel(self)
        self._filter_model = ModelFilterProxy(self)
        self._filter_model.setSourceModel(self._table_model)

        self._build_ui()
        self._apply_branding(current_icon_path())
        self._apply_translations()
        self._load_light_settings()
        self._start_branding_icon_fetch()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)

        self.logo_label = QLabel()
        self.logo_label.setFixedSize(24, 24)
        self.brand_title_label = QLabel("MLCCS")
        brand_font = QFont()
        brand_font.setBold(True)
        brand_font.setPointSize(11)
        self.brand_title_label.setFont(brand_font)
        self.brand_title_label.setStyleSheet("color: #f2f5fb;")
        self.brand_subtitle_label = QLabel("WT VIEWER")
        self.brand_subtitle_label.setStyleSheet("color: #8ea0bb; font-size: 10px; font-weight: 600;")

        brand_text_layout = QVBoxLayout()
        brand_text_layout.setContentsMargins(0, 0, 0, 0)
        brand_text_layout.setSpacing(0)
        brand_text_layout.addWidget(self.brand_title_label)
        brand_text_layout.addWidget(self.brand_subtitle_label)

        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(10, 4, 12, 4)
        brand_layout.setSpacing(8)
        brand_layout.addWidget(self.logo_label)
        brand_layout.addLayout(brand_text_layout)

        brand_widget = QWidget()
        brand_widget.setLayout(brand_layout)
        brand_widget.setStyleSheet("background-color: #161d2b; border: 1px solid #263247; border-radius: 10px;")
        toolbar.addWidget(brand_widget)

        self.select_button = QPushButton("Select War Thunder Folder")
        self.select_button.clicked.connect(self.select_game_folder)
        toolbar.addWidget(self.select_button)

        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.clicked.connect(self.rescan_current_folder)
        toolbar.addWidget(self.rescan_button)

        self.load_button = QPushButton("Load Selected")
        self.load_button.clicked.connect(self.load_selected_model)
        toolbar.addWidget(self.load_button)

        self.search_label = QLabel()
        toolbar.addWidget(self.search_label)
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self._filter_model.set_query)
        toolbar.addWidget(self.search_input, 1)

        self.variant_label = QLabel()
        toolbar.addWidget(self.variant_label)
        self.variant_combo = QComboBox()
        self.variant_combo.setEnabled(False)
        toolbar.addWidget(self.variant_combo)

        self.language_label = QLabel()
        toolbar.addWidget(self.language_label)
        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        toolbar.addWidget(self.language_combo)

        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.path_label)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.count_label = QLabel()
        left_layout.addWidget(self.count_label)

        self.table = QTableView()
        self.table.setModel(self._filter_model)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.doubleClicked.connect(lambda *_: self.load_selected_model())
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        left_layout.addWidget(self.table, 1)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        light_controls = QHBoxLayout()
        right_layout.addLayout(light_controls)
        self.light_heading_label = QLabel()
        light_controls.addWidget(self.light_heading_label)

        self.light_preset_label = QLabel()
        light_controls.addWidget(self.light_preset_label)
        self.light_preset_combo = QComboBox()
        self.light_preset_combo.currentIndexChanged.connect(self._light_preset_changed)
        light_controls.addWidget(self.light_preset_combo)

        self.light_azimuth_label = QLabel()
        light_controls.addWidget(self.light_azimuth_label)
        self.light_azimuth_slider = QSlider(Qt.Horizontal)
        self.light_azimuth_slider.setRange(-180, 180)
        self.light_azimuth_slider.setValue(69)
        self.light_azimuth_slider.valueChanged.connect(self._sync_light_controls)
        light_controls.addWidget(self.light_azimuth_slider, 1)

        self.light_elevation_label = QLabel()
        light_controls.addWidget(self.light_elevation_label)
        self.light_elevation_slider = QSlider(Qt.Horizontal)
        self.light_elevation_slider.setRange(5, 85)
        self.light_elevation_slider.setValue(30)
        self.light_elevation_slider.valueChanged.connect(self._sync_light_controls)
        light_controls.addWidget(self.light_elevation_slider, 1)

        self.light_brightness_label = QLabel()
        light_controls.addWidget(self.light_brightness_label)
        self.light_brightness_slider = QSlider(Qt.Horizontal)
        self.light_brightness_slider.setRange(20, 250)
        self.light_brightness_slider.setValue(125)
        self.light_brightness_slider.valueChanged.connect(self._sync_light_controls)
        light_controls.addWidget(self.light_brightness_slider, 1)

        self.viewport = ModelViewport()
        self.viewport.scene_upload_progress.connect(self._scene_upload_progress)
        self.viewport.scene_upload_finished.connect(self._scene_upload_finished)
        right_layout.addWidget(self.viewport, 1)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.hide()
        layout.addWidget(self.progress)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage(self._t("ready"))

    def _selection_changed(self) -> None:
        self._update_variant_options()
        self._refresh_ui_state()

    def _selected_family(self) -> ModelFamily | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None

        source_index = self._filter_model.mapToSource(indexes[0])
        return self._table_model.item_at(source_index.row())

    def _selected_variant(self) -> ModelVariant | None:
        family = self._selected_family()
        if family is None:
            return None

        variant = self.variant_combo.currentData()
        if isinstance(variant, ModelVariant):
            return variant
        return family.default_variant()

    def _set_progress(self, current: int, total: int, token: str) -> None:
        if total <= 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, total)
            self.progress.setValue(current)

        message = self._translate_progress(token)
        self.progress.setFormat(f"{message} (%v/%m)")
        self.statusBar().showMessage(message)
        self.progress.show()

    def _refresh_ui_state(self) -> None:
        has_selection = self._selected_family() is not None
        can_change_folder = (not self._is_scanning) and (not self._is_loading)

        self.select_button.setEnabled(can_change_folder)
        self.rescan_button.setEnabled((self._game_root is not None) and can_change_folder)
        self.search_input.setEnabled(not self._is_scanning)
        self.language_combo.setEnabled(not self._is_scanning)
        self.table.setEnabled(not self._is_scanning)
        self.variant_combo.setEnabled(
            (not self._is_scanning) and (not self._is_loading) and has_selection and self.variant_combo.count() > 0
        )
        self.load_button.setEnabled(
            (self._game_root is not None) and has_selection and (not self._is_scanning) and (not self._is_loading)
        )

        if not self._is_scanning and not self._is_loading:
            self.progress.hide()

    def select_game_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, self._t("select_folder"))
        if selected:
            self.start_scan(Path(selected))

    def rescan_current_folder(self) -> None:
        if self._game_root is not None:
            self.start_scan(self._game_root)

    def start_scan(self, folder: Path) -> None:
        try:
            validate_game_root(folder)
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                self._t("invalid_folder_title"),
                self._t("invalid_folder", path=str(folder / "content" / "base" / "res")),
            )
            return

        self._thread_pool.clear()
        self._scan_generation += 1
        self._load_request_id += 1
        self._is_scanning = True
        self._is_loading = False
        self._game_root = folder
        self._detected_locale = detect_client_language(folder)
        self._loaded_variant = None
        self._loaded_scene = None
        self._model_items = []
        self._model_families = []
        self.viewport.clear_mesh()
        self._table_model.set_items([])
        self._apply_translations()
        self.path_label.setText(self._t("folder_value", path=str(folder)))
        self.info_label.setText(self._t("scanning_overview"))
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.show()
        self._refresh_ui_state()

        scan_generation = self._scan_generation
        worker = FunctionWorker(scan_rendinst_models, folder, progress=None)
        worker.kwargs["progress"] = worker.signals.progress.emit
        worker.signals.progress.connect(
            lambda current, total, token, generation=scan_generation: self._scan_progress(generation, current, total, token)
        )
        worker.signals.finished.connect(
            lambda items, generation=scan_generation: self._scan_finished(generation, items)
        )
        worker.signals.failed.connect(
            lambda traceback_text, generation=scan_generation: self._worker_failed(generation, None, traceback_text)
        )
        self._thread_pool.start(worker)

    def _scan_progress(self, generation: int, current: int, total: int, token: str) -> None:
        if generation != self._scan_generation:
            return
        self._set_progress(current, total, token)

    def _scan_finished(self, generation: int, items: list[ModelIndexEntry]) -> None:
        if generation != self._scan_generation:
            return

        self._is_scanning = False
        self._model_items = items
        self._model_families = build_model_families(items)
        self._table_model.set_items(self._model_families)
        self.count_label.setText(self._t("models_count", count=f"{len(self._model_families):,}"))
        self.table.resizeColumnsToContents()
        self.statusBar().showMessage(self._t("indexed_models", count=f"{len(self._model_families):,}"))
        self.info_label.setText(self._t("select_prompt"))
        self._update_variant_options()
        self._refresh_ui_state()

    def load_selected_model(self) -> None:
        if self._game_root is None:
            return

        variant = self._selected_variant()
        if variant is None:
            return

        self._thread_pool.clear()
        self._load_request_id += 1
        load_request_id = self._load_request_id
        scan_generation = self._scan_generation

        self._is_loading = True
        self.progress.setRange(0, 0)
        self.progress.setFormat(self._t("load_status", name=variant.entry.name))
        self.progress.show()
        self.info_label.setText(self._t("load_info", name=variant.entry.name, path=variant.entry.group_relpath))
        self.statusBar().showMessage(self._t("load_status", name=variant.entry.name))
        self._refresh_ui_state()

        worker = FunctionWorker(build_render_scene, variant.entry, self._game_root, progress=None)
        worker.kwargs["progress"] = worker.signals.progress.emit
        worker.signals.progress.connect(
            lambda current, total, token, request_id=load_request_id: self._load_progress(request_id, current, total, token)
        )
        worker.signals.finished.connect(
            lambda scene, selected=variant, request_id=load_request_id, generation=scan_generation: self._scene_loaded(
                request_id,
                generation,
                selected,
                scene,
            )
        )
        worker.signals.failed.connect(
            lambda traceback_text, request_id=load_request_id, generation=scan_generation: self._worker_failed(
                generation,
                request_id,
                traceback_text,
            )
        )
        self._thread_pool.start(worker)

    def _load_progress(self, request_id: int, current: int, total: int, token: str) -> None:
        if request_id != self._load_request_id or self._is_scanning:
            return
        self._set_progress(current, total, token)

    def _scene_loaded(
        self,
        request_id: int,
        generation: int,
        variant: ModelVariant,
        scene: RenderScene,
    ) -> None:
        if request_id != self._load_request_id or generation != self._scan_generation:
            return

        self._loaded_variant = variant
        self._loaded_scene = scene
        self.viewport.set_scene(scene)
        self.progress.setRange(0, max(1, len(scene.batches)))
        self.progress.setValue(0)
        self.progress.setFormat(f"{self._t('upload_scene', name=variant.entry.name)} (%v/%m)")
        self.info_label.setText(
            self._t(
                "load_summary",
                name=variant.entry.name,
                pack=variant.entry.pack_name,
                path=variant.entry.group_relpath,
                vertices=f"{scene.vertex_count:,}",
                faces=f"{scene.face_count:,}",
                objects=f"{scene.object_count:,}",
                textured=f"{scene.textured_batch_count:,}",
                normal_mapped=f"{scene.normal_mapped_batch_count:,}",
                controls=self._t("controls"),
            )
        )
        self.statusBar().showMessage(self._t("upload_scene", name=variant.entry.name))
        self._refresh_ui_state()

    def _worker_failed(self, generation: int, request_id: int | None, traceback_text: str) -> None:
        if generation != self._scan_generation:
            return
        if request_id is not None and request_id != self._load_request_id:
            return

        self._is_scanning = False
        self._is_loading = False
        self._refresh_ui_state()
        self.statusBar().showMessage(self._t("operation_failed"))
        QMessageBox.critical(self, self._t("error_title"), traceback_text)

    def _scene_upload_progress(self, current: int, total: int) -> None:
        if not self._is_loading or self._loaded_variant is None:
            return

        self.progress.setRange(0, max(1, total))
        self.progress.setValue(current)
        message = self._t("upload_scene", name=self._loaded_variant.entry.name)
        self.progress.setFormat(f"{message} (%v/%m)")
        self.statusBar().showMessage(message)
        self.progress.show()

    def _scene_upload_finished(self) -> None:
        if not self._is_loading or self._loaded_variant is None:
            return

        self._is_loading = False
        self.statusBar().showMessage(self._t("loaded_status", name=self._loaded_variant.entry.name))
        self._refresh_ui_state()

    def _current_locale(self) -> str:
        mode = self.language_combo.currentData()
        if mode == "auto":
            return self._detected_locale
        return mode or "en"

    def _apply_branding(self, icon_path: Path | None) -> None:
        if icon_path is None or not icon_path.exists():
            self.logo_label.clear()
            return

        icon = QIcon(str(icon_path))
        if icon.isNull():
            self.logo_label.clear()
            return

        self.setWindowIcon(icon)
        self.logo_label.setPixmap(icon.pixmap(24, 24))

    def _start_branding_icon_fetch(self) -> None:
        cache_path = cached_icon_path()
        if cache_path.exists() and cache_path.stat().st_size > 0:
            return

        worker = FunctionWorker(fetch_and_cache_icon)
        worker.signals.finished.connect(self._branding_icon_ready)
        worker.signals.failed.connect(lambda _traceback_text: None)
        self._aux_thread_pool.start(worker)

    def _branding_icon_ready(self, icon_path: Path | None) -> None:
        self._apply_branding(icon_path)

    def _default_light_values(self) -> dict[str, int]:
        return LIGHT_PRESETS["balanced"].copy()

    def _load_light_settings(self) -> None:
        defaults = self._default_light_values()
        saved_preset = str(self._settings.value("lighting/preset", "balanced"))
        azimuth = int(self._settings.value("lighting/azimuth", defaults["azimuth"]))
        elevation = int(self._settings.value("lighting/elevation", defaults["elevation"]))
        brightness = int(self._settings.value("lighting/brightness", defaults["brightness"]))

        for slider, value in (
            (self.light_azimuth_slider, azimuth),
            (self.light_elevation_slider, elevation),
            (self.light_brightness_slider, brightness),
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)

        self._set_light_preset_selection(saved_preset if saved_preset in LIGHT_PRESETS else LIGHT_CUSTOM_KEY)
        self._sync_light_controls()

    def _save_light_settings(self, preset_key: str) -> None:
        self._settings.setValue("lighting/preset", preset_key)
        self._settings.setValue("lighting/azimuth", self.light_azimuth_slider.value())
        self._settings.setValue("lighting/elevation", self.light_elevation_slider.value())
        self._settings.setValue("lighting/brightness", self.light_brightness_slider.value())
        self._settings.sync()

    def _rebuild_light_preset_options(self, selected_key: str) -> None:
        self.light_preset_combo.blockSignals(True)
        self.light_preset_combo.clear()
        self.light_preset_combo.addItem(self._t("light_preset_custom"), LIGHT_CUSTOM_KEY)
        for preset_key in ("balanced", "studio", "overcast", "side"):
            self.light_preset_combo.addItem(self._t(f"light_preset_{preset_key}"), preset_key)
        self._set_light_preset_selection(selected_key)
        self.light_preset_combo.blockSignals(False)

    def _set_light_preset_selection(self, preset_key: str) -> None:
        index = self.light_preset_combo.findData(preset_key)
        if index < 0:
            index = self.light_preset_combo.findData(LIGHT_CUSTOM_KEY)
        if index >= 0:
            self.light_preset_combo.blockSignals(True)
            self.light_preset_combo.setCurrentIndex(index)
            self.light_preset_combo.blockSignals(False)

    def _match_light_preset_key(self) -> str:
        azimuth = self.light_azimuth_slider.value()
        elevation = self.light_elevation_slider.value()
        brightness = self.light_brightness_slider.value()
        for preset_key, values in LIGHT_PRESETS.items():
            if (
                values["azimuth"] == azimuth
                and values["elevation"] == elevation
                and values["brightness"] == brightness
            ):
                return preset_key
        return LIGHT_CUSTOM_KEY

    def _light_preset_changed(self) -> None:
        preset_key = self.light_preset_combo.currentData()
        if not isinstance(preset_key, str) or preset_key == LIGHT_CUSTOM_KEY or preset_key not in LIGHT_PRESETS:
            self._save_light_settings(self._match_light_preset_key())
            return

        preset = LIGHT_PRESETS[preset_key]
        for slider, value in (
            (self.light_azimuth_slider, preset["azimuth"]),
            (self.light_elevation_slider, preset["elevation"]),
            (self.light_brightness_slider, preset["brightness"]),
        ):
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
        self._sync_light_controls()

    def _sync_light_controls(self) -> None:
        azimuth = float(self.light_azimuth_slider.value())
        elevation = float(self.light_elevation_slider.value())
        brightness = self.light_brightness_slider.value() / 100.0
        self.viewport.set_light_angles(azimuth, elevation)
        self.viewport.set_light_intensity(brightness)
        matched_preset = self._match_light_preset_key()
        self._set_light_preset_selection(matched_preset)
        self._save_light_settings(matched_preset)
        self._refresh_light_labels()

    def _refresh_light_labels(self) -> None:
        self.light_heading_label.setText(self._t("lighting"))
        self.light_preset_label.setText(self._t("light_preset"))
        self.light_azimuth_label.setText(self._t("light_azimuth", value=str(self.light_azimuth_slider.value())))
        self.light_elevation_label.setText(
            self._t("light_elevation", value=str(self.light_elevation_slider.value()))
        )
        self.light_brightness_label.setText(
            self._t("light_brightness", value=f"{self.light_brightness_slider.value()}%")
        )

    def _t(self, key: str, **kwargs: object) -> str:
        return tr(self._current_locale(), key, **kwargs)

    def _apply_translations(self) -> None:
        selected_language = self.language_combo.currentData() if self.language_combo.count() else "auto"
        self.setWindowTitle(self._t("window_title"))
        self.select_button.setText(self._t("select_folder"))
        self.rescan_button.setText(self._t("rescan"))
        self.load_button.setText(self._t("load_selected"))
        self.search_label.setText(self._t("search"))
        self.search_input.setPlaceholderText(self._t("search_placeholder"))
        self.variant_label.setText(self._t("variant"))
        self.language_label.setText(self._t("language"))
        self.brand_subtitle_label.setText(self._t("brand_subtitle"))
        self._rebuild_light_preset_options(self._match_light_preset_key())
        self._refresh_light_labels()

        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(self._t("language_auto"), "auto")
        self.language_combo.addItem(self._t("language_en"), "en")
        self.language_combo.addItem(self._t("language_zh"), "zh")
        self.language_combo.addItem(self._t("language_ja"), "ja")
        current = self.language_combo.findData(selected_language)
        if current < 0:
            current = self.language_combo.findData("auto")
        if current >= 0:
            self.language_combo.setCurrentIndex(current)
        self.language_combo.blockSignals(False)

        self._table_model.set_locale(self._current_locale())
        self._update_variant_options()

        if self._game_root is None:
            self.path_label.setText(self._t("folder_none"))
        else:
            self.path_label.setText(self._t("folder_value", path=str(self._game_root)))

        self.count_label.setText(self._t("models_count", count=f"{len(self._model_families):,}"))
        if self._loaded_variant is not None and self._loaded_scene is not None:
            self.info_label.setText(
                self._t(
                    "load_summary",
                    name=self._loaded_variant.entry.name,
                    pack=self._loaded_variant.entry.pack_name,
                    path=self._loaded_variant.entry.group_relpath,
                    vertices=f"{self._loaded_scene.vertex_count:,}",
                    faces=f"{self._loaded_scene.face_count:,}",
                    objects=f"{self._loaded_scene.object_count:,}",
                    textured=f"{self._loaded_scene.textured_batch_count:,}",
                    normal_mapped=f"{self._loaded_scene.normal_mapped_batch_count:,}",
                    controls=self._t("controls"),
                )
            )
        elif self._game_root is None:
            self.info_label.setText(self._t("select_prompt"))
        elif not self._is_scanning:
            self.info_label.setText(self._t("select_prompt"))

        if not self._is_scanning and not self._is_loading:
            self.statusBar().showMessage(self._t("ready"))

        self.table.resizeColumnsToContents()
        self._refresh_ui_state()

    def _language_changed(self) -> None:
        self._apply_translations()

    def _translate_progress(self, token: str) -> str:
        prefix, _, name = token.partition("::")
        if prefix == "desc":
            return self._t("scan_desc", name=name)
        if prefix == "texture":
            return self._t("scan_texture", name=name)
        if prefix == "group":
            return self._t("scan_group", name=name)
        if prefix == "scene":
            return self._t("scan_scene", name=name)
        return token

    def _update_variant_options(self) -> None:
        family = self._selected_family()
        previous_entry = self.variant_combo.currentData()
        previous_key = previous_entry.key if isinstance(previous_entry, ModelVariant) else None

        self.variant_combo.blockSignals(True)
        self.variant_combo.clear()

        if family is not None:
            for variant in family.variants:
                self.variant_combo.addItem(self._variant_display_text(family, variant), variant)

            current_index = 0
            if previous_key is not None:
                for index in range(self.variant_combo.count()):
                    variant = self.variant_combo.itemData(index)
                    if isinstance(variant, ModelVariant) and variant.key == previous_key:
                        current_index = index
                        break
            self.variant_combo.setCurrentIndex(current_index)

        self.variant_combo.blockSignals(False)

    def _variant_display_text(self, family: ModelFamily, variant: ModelVariant) -> str:
        if variant.key in {"default", "dmg", "xray"}:
            label = self._t(f"variant_{variant.key}")
        else:
            label = variant.label

        if variant.key == "default" and variant.entry.name == family.base_name:
            return label
        return f"{label} ({variant.entry.name})"
