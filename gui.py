import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QProgressBar,
    QDoubleSpinBox, QCheckBox, QComboBox, QSpinBox
)
from PySide6.QtCore import QThread, Signal
import main as pipeline

class Worker(QThread):
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, int)

    def __init__(self, video, gps, output, fields=None):
        super().__init__()
        self.video, self.gps, self.output = video, gps, output
        self.fields = fields or {}

    def run(self):
        try:
            fields = pipeline.DEFAULT_FIELDS.copy()
            fields.update(self.fields)
            # include source file base names for optional display
            import os
            if self.video:
                fields["video_name"] = os.path.basename(self.video)
            if self.gps:
                fields["gps_name"] = os.path.basename(self.gps)

            pipeline.run(self.video, self.gps, self.output, fields,
                         progress_callback=lambda i, total: self.progress.emit(i, total))
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Drone Geo-Tagger")
        self.resize(440, 280)
        self.video_path = None
        self.gps_path = None
        self.output_path = "output_geotagged.mp4"
        self.font_scale = 0.6
        self.alpha = 0.5
        self.position = pipeline.DEFAULT_FIELDS.get("position", "bottom-left")
        self.minimap_enabled = False
        self.minimap_zoom = 16
        self.minimap_size = 200
        self.minimap_position = pipeline.DEFAULT_FIELDS.get("minimap_position", "top-right")
        self.minimap_marker_shape = "triangle"
        self.minimap_marker_color = "red"
        self.minimap_trail_thickness = 4
        self.minimap_source = pipeline.DEFAULT_FIELDS.get("minimap_source", "satellite")

        layout = QVBoxLayout()
        self.video_label = QLabel("No video selected")
        self.gps_label = QLabel("No GPS/SRT file selected (optional)")
        self.output_label = QLabel(f"Output: {self.output_path}")

        video_btn = QPushButton("📁 Browse for Drone Video")
        video_btn.clicked.connect(self.select_video)

        gps_btn = QPushButton("📁 Browse for GPS File (Optional)")
        gps_btn.clicked.connect(self.select_gps)

        output_btn = QPushButton("📁 Choose Output Location")
        output_btn.clicked.connect(self.select_output)

        self.font_label = QLabel("Text size")
        self.font_size = QDoubleSpinBox()
        self.font_size.setRange(0.3, 2.0)
        self.font_size.setSingleStep(0.1)
        self.font_size.setValue(self.font_scale)
        self.font_size.valueChanged.connect(self.on_font_size_changed)

        self.alpha_label = QLabel("Text background transparency")
        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.0, 1.0)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.setValue(self.alpha)
        self.alpha_spin.valueChanged.connect(lambda v: setattr(self, 'alpha', float(v)))

        self.position_label = QLabel("Position")
        self.position_box = QComboBox()
        self.position_box.addItems(["top-left", "top-right", "bottom-left", "bottom-right"])
        self.position_box.setCurrentText(self.position)
        self.position_box.currentTextChanged.connect(lambda t: setattr(self, 'position', t))

        # Field toggles
        self.chk_timestamp = QCheckBox("Show time")
        self.chk_timestamp.setChecked(False)
        self.chk_altitude = QCheckBox("Show altitude")
        self.chk_altitude.setChecked(False)
        self.chk_place = QCheckBox("Show city/state/country")
        self.chk_place.setChecked(False)
        self.chk_speed = QCheckBox("Show speed")
        self.chk_speed.setChecked(False)
        self.chk_heading = QCheckBox("Show heading")
        self.chk_heading.setChecked(False)
        self.chk_distance_enable = QCheckBox("Enable distance")
        self.chk_distance_enable.setChecked(True)
        self.chk_distance_enable.stateChanged.connect(self.update_distance_controls)
        self.chk_distance = QCheckBox("Show distance (m)")
        self.chk_distance.setChecked(True)
        self.chk_distance_km = QCheckBox("Show distance (km)")
        self.chk_distance_km.setChecked(True)
        self.chk_src = QCheckBox("Show source file names")
        self.chk_src.setChecked(False)

        self.chk_minimap = QCheckBox("Show minimap")
        self.chk_minimap.setChecked(False)
        self.chk_minimap.stateChanged.connect(self.update_minimap_controls)

        self.minimap_zoom_label = QLabel("Minimap zoom")
        self.minimap_zoom_box = QSpinBox()
        self.minimap_zoom_box.setRange(1, 20)
        self.minimap_zoom_box.setValue(self.minimap_zoom)
        self.minimap_zoom_box.valueChanged.connect(lambda v: setattr(self, 'minimap_zoom', int(v)))

        self.minimap_size_label = QLabel("Minimap size")
        self.minimap_size_box = QSpinBox()
        self.minimap_size_box.setRange(80, 400)
        self.minimap_size_box.setSingleStep(10)
        self.minimap_size_box.setValue(self.minimap_size)
        self.minimap_size_box.valueChanged.connect(lambda v: setattr(self, 'minimap_size', int(v)))

        self.minimap_position_label = QLabel("Minimap position")
        self.minimap_position_box = QComboBox()
        self.minimap_position_box.addItems(["top-left", "top-right", "bottom-left", "bottom-right"])
        self.minimap_position_box.setCurrentText(self.minimap_position)
        self.minimap_position_box.currentTextChanged.connect(lambda t: setattr(self, 'minimap_position', t))

        self.minimap_marker_shape_label = QLabel("Marker shape")
        self.minimap_marker_shape_box = QComboBox()
        self.minimap_marker_shape_box.addItems(["triangle", "circle", "square"])
        self.minimap_marker_shape_box.setCurrentText(self.minimap_marker_shape)
        self.minimap_marker_shape_box.currentTextChanged.connect(lambda t: setattr(self, 'minimap_marker_shape', t))

        self.minimap_marker_color_label = QLabel("Marker color")
        self.minimap_marker_color_box = QComboBox()
        self.minimap_marker_color_box.addItems(["red", "yellow", "white", "green", "blue", "orange"])
        self.minimap_marker_color_box.setCurrentText(self.minimap_marker_color)
        self.minimap_marker_color_box.currentTextChanged.connect(lambda t: setattr(self, 'minimap_marker_color', t))

        self.minimap_source_label = QLabel("Map source")
        self.minimap_source_box = QComboBox()
        self.minimap_source_box.addItems(["satellite", "roadmap"])
        self.minimap_source_box.setCurrentText(self.minimap_source)
        self.minimap_source_box.currentTextChanged.connect(lambda t: setattr(self, 'minimap_source', t))

        self.minimap_trail_thickness_label = QLabel("Trail thickness")
        self.minimap_trail_thickness_box = QSpinBox()
        self.minimap_trail_thickness_box.setRange(1, 20)
        self.minimap_trail_thickness_box.setValue(self.minimap_trail_thickness)
        self.minimap_trail_thickness_box.valueChanged.connect(lambda v: setattr(self, 'minimap_trail_thickness', int(v)))

        self.update_distance_controls()
        self.update_minimap_controls()

        self.start_btn = QPushButton("▶ Start Processing")
        self.start_btn.clicked.connect(self.start)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()

        for w in (video_btn, self.video_label, gps_btn, self.gps_label,
                  output_btn, self.output_label, self.font_label, self.font_size,
                  self.alpha_label, self.alpha_spin, self.position_label, self.position_box,
                  self.chk_timestamp, self.chk_altitude, self.chk_place, self.chk_speed, self.chk_heading,
                  self.chk_distance, self.chk_distance_km, self.chk_src,
                                    self.chk_minimap, self.minimap_zoom_label, self.minimap_zoom_box,
                                    self.minimap_size_label, self.minimap_size_box,
                                    self.minimap_position_label, self.minimap_position_box,
                                    self.minimap_marker_shape_label, self.minimap_marker_shape_box,
                                    self.minimap_marker_color_label, self.minimap_marker_color_box,
                                    self.minimap_source_label, self.minimap_source_box,
                                    self.minimap_trail_thickness_label, self.minimap_trail_thickness_box,
                  self.start_btn, self.progress):
            layout.addWidget(w)
        self.setLayout(layout)

    def select_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Drone Video", "", "Videos (*.mp4 *.mov *.avi *.mkv)"
        )
        if path:
            self.video_path = path
            self.video_label.setText(f"Video: {path.split('/')[-1]}")

    def select_gps(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GPS File", "", "Data Files (*.csv *.xlsx *.json *.txt *.srt)"
        )
        if path:
            self.gps_path = path
            self.gps_label.setText(f"GPS/SRT: {path.split('/')[-1]}")

    def select_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Video As", "output_geotagged.mp4", "MP4 Video (*.mp4)"
        )
        if path:
            self.output_path = path
            self.output_label.setText(f"Output: {path}")

    def on_font_size_changed(self, value):
        self.font_scale = float(value)

    def update_minimap_controls(self, *args):
        enabled = self.chk_minimap.isChecked()
        self.minimap_zoom_label.setEnabled(enabled)
        self.minimap_zoom_box.setEnabled(enabled)
        self.minimap_size_label.setEnabled(enabled)
        self.minimap_size_box.setEnabled(enabled)
        self.minimap_position_label.setEnabled(enabled)
        self.minimap_position_box.setEnabled(enabled)
        self.minimap_marker_shape_label.setEnabled(enabled)
        self.minimap_marker_shape_box.setEnabled(enabled)
        self.minimap_marker_color_label.setEnabled(enabled)
        self.minimap_marker_color_box.setEnabled(enabled)
        self.minimap_source_label.setEnabled(enabled)
        self.minimap_source_box.setEnabled(enabled)
        self.minimap_trail_thickness_label.setEnabled(enabled)
        self.minimap_trail_thickness_box.setEnabled(enabled)

    def update_distance_controls(self, *args):
        enabled = self.chk_distance_enable.isChecked()
        self.chk_distance.setEnabled(enabled)
        self.chk_distance_km.setEnabled(enabled)
        if not enabled:
            self.chk_distance.setChecked(False)
            self.chk_distance_km.setChecked(False)

    def start(self):
        if not self.video_path:
            self.video_label.setText("⚠ Please select a video first.")
            return
        self.progress.show()
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)
        # Build the fields dict from UI controls
        fields = pipeline.DEFAULT_FIELDS.copy()
        fields["font_scale"] = float(self.font_size.value())
        fields["alpha"] = float(self.alpha_spin.value())
        fields["position"] = str(self.position_box.currentText())
        fields["timestamp"] = bool(self.chk_timestamp.isChecked())
        fields["altitude"] = bool(self.chk_altitude.isChecked())
        fields["place"] = bool(self.chk_place.isChecked())
        fields["speed"] = bool(self.chk_speed.isChecked())
        fields["heading"] = bool(self.chk_heading.isChecked())
        fields["distance_enabled"] = bool(self.chk_distance_enable.isChecked())
        fields["distance"] = bool(self.chk_distance_enable.isChecked() and self.chk_distance.isChecked())
        fields["distance_km"] = bool(self.chk_distance_enable.isChecked() and self.chk_distance_km.isChecked())
        fields["show_src_info"] = bool(self.chk_src.isChecked())
        fields["minimap_enabled"] = bool(self.chk_minimap.isChecked())
        fields["minimap_zoom"] = int(self.minimap_zoom_box.value())
        fields["minimap_size"] = int(self.minimap_size_box.value())
        fields["minimap_position"] = str(self.minimap_position_box.currentText())
        fields["minimap_marker_shape"] = str(self.minimap_marker_shape_box.currentText())
        fields["minimap_marker_color"] = str(self.minimap_marker_color_box.currentText())
        fields["minimap_source"] = str(self.minimap_source_box.currentText())
        fields["minimap_trail_thickness"] = int(self.minimap_trail_thickness_box.value())

        self.worker = Worker(self.video_path, self.gps_path, self.output_path, fields)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_done)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_progress(self, current, total):
        pct = int((current / total) * 100) if total else 0
        self.progress.setValue(pct)

    def on_done(self):
        self.progress.setValue(100)
        self.start_btn.setEnabled(True)
        self.output_label.setText(f"✅ Done! Saved to: {self.output_path}")

    def on_error(self, msg):
        self.progress.hide()
        self.start_btn.setEnabled(True)
        self.output_label.setText(f"❌ Error: {msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())