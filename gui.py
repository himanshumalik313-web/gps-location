import sys
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog, QLabel, QProgressBar,
    QDoubleSpinBox, QCheckBox, QComboBox, QSpinBox, QLineEdit, QScrollArea, QHBoxLayout
)
from PySide6.QtCore import QThread, Signal
import main as pipeline
from overlay import FONT_STYLES, NAMED_COLORS

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
        self.resize(900, 1020)
        self.video_path = None
        self.gps_path = None
        self.output_path = "output_geotagged.mp4"
        self.font_scale = 0.6
        self.alpha = 0.5
        self.overlay_line_spacing = 6
        self.position = pipeline.DEFAULT_FIELDS.get("position", "bottom-left")
        self.guide_enabled = bool(pipeline.DEFAULT_FIELDS.get("guide_enabled", True))
        self.guide_offset = int(pipeline.DEFAULT_FIELDS.get("guide_offset", 150))
        self.guide_center_color = pipeline.DEFAULT_FIELDS.get("guide_center_color", "yellow")
        self.guide_side_color = pipeline.DEFAULT_FIELDS.get("guide_side_color", "white")
        self.guide_thickness = int(pipeline.DEFAULT_FIELDS.get("guide_thickness", 3))
        self.guide_dash_length = int(pipeline.DEFAULT_FIELDS.get("guide_dash_length", 18))
        self.guide_gap_length = int(pipeline.DEFAULT_FIELDS.get("guide_gap_length", 14))
        self.guide_length_pct = float(pipeline.DEFAULT_FIELDS.get("guide_length_pct", 0.85))
        self.guide_center_label = pipeline.DEFAULT_FIELDS.get("guide_center_label", "CL")
        self.guide_left_label = pipeline.DEFAULT_FIELDS.get("guide_left_label", "LEFT")
        self.guide_right_label = pipeline.DEFAULT_FIELDS.get("guide_right_label", "RIGHT")
        self.guide_label_font_scale = float(pipeline.DEFAULT_FIELDS.get("guide_label_font_scale", 0.7))
        self.guide_label_thickness = int(pipeline.DEFAULT_FIELDS.get("guide_label_thickness", 1))
        self.banner_enabled = bool(pipeline.DEFAULT_FIELDS.get("banner_enabled", False))
        self.banner_height = int(pipeline.DEFAULT_FIELDS.get("banner_height", 72))
        self.banner_color = pipeline.DEFAULT_FIELDS.get("banner_color", "black")
        self.banner_alpha = float(pipeline.DEFAULT_FIELDS.get("banner_alpha", 0.45))
        self.banner_border_color = pipeline.DEFAULT_FIELDS.get("banner_border_color", "white")
        self.banner_border_thickness = int(pipeline.DEFAULT_FIELDS.get("banner_border_thickness", 1))
        self.minimap_enabled = False
        self.minimap_zoom = int(pipeline.DEFAULT_FIELDS.get("minimap_zoom", 16))
        self.minimap_size = int(pipeline.DEFAULT_FIELDS.get("minimap_size", 200))
        self.minimap_position = pipeline.DEFAULT_FIELDS.get("minimap_position", "top-right")
        self.minimap_custom_position = bool(pipeline.DEFAULT_FIELDS.get("minimap_custom_position", False))
        self.minimap_x = 20
        self.minimap_y = 20
        self.minimap_marker_shape = pipeline.DEFAULT_FIELDS.get("minimap_marker_shape", "triangle")
        self.minimap_marker_color = pipeline.DEFAULT_FIELDS.get("minimap_marker_color", "red")
        self.minimap_trail_thickness = int(pipeline.DEFAULT_FIELDS.get("minimap_trail_thickness", 4))
        self.minimap_trail_color = pipeline.DEFAULT_FIELDS.get("minimap_trail_color", "red")
        self.minimap_source = pipeline.DEFAULT_FIELDS.get("minimap_source", "satellite")

        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

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

        self.overlay_line_spacing_label = QLabel("Info line spacing")
        self.overlay_line_spacing_box = QSpinBox()
        self.overlay_line_spacing_box.setRange(0, 40)
        self.overlay_line_spacing_box.setValue(self.overlay_line_spacing)
        self.overlay_line_spacing_box.valueChanged.connect(lambda v: setattr(self, 'overlay_line_spacing', int(v)))

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

        self.chk_guides = QCheckBox("Show guide lines")
        self.chk_guides.setChecked(self.guide_enabled)
        self.guide_offset_label = QLabel("Guide separation (px)")
        self.guide_offset_box = QSpinBox()
        self.guide_offset_box.setRange(10, 1200)
        self.guide_offset_box.setValue(self.guide_offset)
        self.guide_center_color_label = QLabel("Center line color")
        self.guide_center_color_box = QComboBox()
        self.guide_center_color_box.addItems(list(NAMED_COLORS.keys()))
        self.guide_center_color_box.setCurrentText(self.guide_center_color)
        self.guide_side_color_label = QLabel("Side line color")
        self.guide_side_color_box = QComboBox()
        self.guide_side_color_box.addItems(list(NAMED_COLORS.keys()))
        self.guide_side_color_box.setCurrentText(self.guide_side_color)
        self.guide_thickness_label = QLabel("Guide thickness")
        self.guide_thickness_box = QSpinBox()
        self.guide_thickness_box.setRange(1, 20)
        self.guide_thickness_box.setValue(self.guide_thickness)
        self.guide_dash_length_label = QLabel("Dash length")
        self.guide_dash_length_box = QSpinBox()
        self.guide_dash_length_box.setRange(1, 100)
        self.guide_dash_length_box.setValue(self.guide_dash_length)
        self.guide_gap_length_label = QLabel("Gap length")
        self.guide_gap_length_box = QSpinBox()
        self.guide_gap_length_box.setRange(1, 100)
        self.guide_gap_length_box.setValue(self.guide_gap_length)
        self.guide_length_pct_label = QLabel("Guide vertical length")
        self.guide_length_pct_box = QDoubleSpinBox()
        self.guide_length_pct_box.setRange(0.1, 1.0)
        self.guide_length_pct_box.setSingleStep(0.05)
        self.guide_length_pct_box.setValue(self.guide_length_pct)
        self.guide_center_label_label = QLabel("Center label")
        self.guide_center_label_box = QLineEdit(self.guide_center_label)
        self.guide_left_label_label = QLabel("Left label")
        self.guide_left_label_box = QLineEdit(self.guide_left_label)
        self.guide_right_label_label = QLabel("Right label")
        self.guide_right_label_box = QLineEdit(self.guide_right_label)
        self.guide_label_font_scale_label = QLabel("Label size")
        self.guide_label_font_scale_box = QDoubleSpinBox()
        self.guide_label_font_scale_box.setRange(0.2, 3.0)
        self.guide_label_font_scale_box.setSingleStep(0.1)
        self.guide_label_font_scale_box.setValue(self.guide_label_font_scale)
        self.guide_label_thickness_label = QLabel("Label thickness")
        self.guide_label_thickness_box = QSpinBox()
        self.guide_label_thickness_box.setRange(1, 10)
        self.guide_label_thickness_box.setValue(self.guide_label_thickness)

        self.chk_banner = QCheckBox("Show top border")
        self.chk_banner.setChecked(self.banner_enabled)
        self.banner_height_label = QLabel("Border height")
        self.banner_height_box = QSpinBox()
        self.banner_height_box.setRange(0, 240)
        self.banner_height_box.setValue(self.banner_height)
        self.banner_color_label = QLabel("Border color")
        self.banner_color_box = QComboBox()
        self.banner_color_box.addItems(list(NAMED_COLORS.keys()))
        self.banner_color_box.setCurrentText(self.banner_color)
        self.banner_alpha_label = QLabel("Border transparency")
        self.banner_alpha_box = QDoubleSpinBox()
        self.banner_alpha_box.setRange(0.0, 1.0)
        self.banner_alpha_box.setSingleStep(0.05)
        self.banner_alpha_box.setValue(self.banner_alpha)
        self.banner_border_color_label = QLabel("Border outline color")
        self.banner_border_color_box = QComboBox()
        self.banner_border_color_box.addItems(list(NAMED_COLORS.keys()))
        self.banner_border_color_box.setCurrentText(self.banner_border_color)
        self.banner_border_thickness_label = QLabel("Border outline thickness")
        self.banner_border_thickness_box = QSpinBox()
        self.banner_border_thickness_box.setRange(0, 10)
        self.banner_border_thickness_box.setValue(self.banner_border_thickness)

        self.banner_slots = []
        banner_defaults = [
            {"enabled": True, "text": "Kawardha Bypass", "x": 430, "y": 20, "angle": 0, "font_scale": 1.15, "font": "simplex", "color": "white"},
            {"enabled": True, "text": "km 1+699", "x": 430, "y": 46, "angle": 0, "font_scale": 0.75, "font": "duplex", "color": "white"},
            {"enabled": False, "text": "", "x": 700, "y": 20, "angle": 0, "font_scale": 0.65, "font": "simplex", "color": "white"},
        ]
        for index, defaults in enumerate(banner_defaults, start=1):
            slot_widget = QWidget()
            slot_layout = QHBoxLayout(slot_widget)
            enabled_box = QCheckBox(f"Text {index}")
            enabled_box.setChecked(defaults["enabled"])
            text_box = QLineEdit(defaults["text"])
            x_box = QSpinBox()
            x_box.setRange(0, 4000)
            x_box.setValue(defaults["x"])
            y_box = QSpinBox()
            y_box.setRange(0, 4000)
            y_box.setValue(defaults["y"])
            angle_box = QSpinBox()
            angle_box.setRange(-180, 180)
            angle_box.setValue(defaults["angle"])
            size_box = QDoubleSpinBox()
            size_box.setRange(0.2, 4.0)
            size_box.setSingleStep(0.1)
            size_box.setValue(defaults["font_scale"])
            font_box = QComboBox()
            font_box.addItems(list(FONT_STYLES.keys()))
            font_box.setCurrentText(defaults["font"])
            color_box = QComboBox()
            color_box.addItems(list(NAMED_COLORS.keys()))
            color_box.setCurrentText(defaults["color"])
            slot_layout.addWidget(enabled_box)
            slot_layout.addWidget(QLabel("Text"))
            slot_layout.addWidget(text_box)
            slot_layout.addWidget(QLabel("x"))
            slot_layout.addWidget(x_box)
            slot_layout.addWidget(QLabel("y"))
            slot_layout.addWidget(y_box)
            slot_layout.addWidget(QLabel("rot"))
            slot_layout.addWidget(angle_box)
            slot_layout.addWidget(QLabel("size"))
            slot_layout.addWidget(size_box)
            slot_layout.addWidget(QLabel("font"))
            slot_layout.addWidget(font_box)
            slot_layout.addWidget(QLabel("color"))
            slot_layout.addWidget(color_box)
            self.banner_slots.append({
                "widget": slot_widget,
                "enabled": enabled_box,
                "text": text_box,
                "x": x_box,
                "y": y_box,
                "angle": angle_box,
                "size": size_box,
                "font": font_box,
                "color": color_box,
            })

        self.chk_minimap = QCheckBox("Show minimap")
        self.chk_minimap.setChecked(False)
        self.chk_minimap.stateChanged.connect(self.update_minimap_controls)
        self.minimap_custom_pos_check = QCheckBox("Use custom minimap x/y")
        self.minimap_custom_pos_check.setChecked(self.minimap_custom_position)
        self.minimap_custom_pos_check.stateChanged.connect(self.update_minimap_controls)

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

        self.minimap_x_label = QLabel("Minimap x")
        self.minimap_x_box = QSpinBox()
        self.minimap_x_box.setRange(0, 5000)
        self.minimap_x_box.setValue(self.minimap_x)
        self.minimap_y_label = QLabel("Minimap y")
        self.minimap_y_box = QSpinBox()
        self.minimap_y_box.setRange(0, 5000)
        self.minimap_y_box.setValue(self.minimap_y)

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

        self.minimap_trail_color_label = QLabel("Trail color")
        self.minimap_trail_color_box = QComboBox()
        self.minimap_trail_color_box.addItems(list(NAMED_COLORS.keys()))
        self.minimap_trail_color_box.setCurrentText(self.minimap_trail_color)

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
                  self.overlay_line_spacing_label, self.overlay_line_spacing_box,
                  self.chk_timestamp, self.chk_altitude, self.chk_place, self.chk_speed, self.chk_heading,
                  self.chk_distance_enable, self.chk_distance, self.chk_distance_km, self.chk_src,
                  self.chk_guides, self.guide_offset_label, self.guide_offset_box,
                  self.guide_center_color_label, self.guide_center_color_box,
                  self.guide_side_color_label, self.guide_side_color_box,
                  self.guide_thickness_label, self.guide_thickness_box,
                  self.guide_dash_length_label, self.guide_dash_length_box,
                  self.guide_gap_length_label, self.guide_gap_length_box,
                  self.guide_length_pct_label, self.guide_length_pct_box,
                  self.guide_center_label_label, self.guide_center_label_box,
                  self.guide_left_label_label, self.guide_left_label_box,
                  self.guide_right_label_label, self.guide_right_label_box,
                  self.guide_label_font_scale_label, self.guide_label_font_scale_box,
                  self.guide_label_thickness_label, self.guide_label_thickness_box,
                  self.chk_banner, self.banner_height_label, self.banner_height_box,
                  self.banner_color_label, self.banner_color_box,
                  self.banner_alpha_label, self.banner_alpha_box,
                  self.banner_border_color_label, self.banner_border_color_box,
                  self.banner_border_thickness_label, self.banner_border_thickness_box,
                  *[item for slot in self.banner_slots for item in (slot["widget"],)],
                  self.chk_minimap, self.minimap_zoom_label, self.minimap_zoom_box,
                  self.minimap_size_label, self.minimap_size_box,
                  self.minimap_position_label, self.minimap_position_box,
                  self.minimap_custom_pos_check, self.minimap_x_label, self.minimap_x_box,
                  self.minimap_y_label, self.minimap_y_box,
                  self.minimap_marker_shape_label, self.minimap_marker_shape_box,
                  self.minimap_marker_color_label, self.minimap_marker_color_box,
                  self.minimap_trail_color_label, self.minimap_trail_color_box,
                  self.minimap_source_label, self.minimap_source_box,
                  self.minimap_trail_thickness_label, self.minimap_trail_thickness_box,
                  self.start_btn, self.progress):
            layout.addWidget(w)

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
        self.minimap_custom_pos_check.setEnabled(enabled)
        custom_enabled = enabled and self.minimap_custom_pos_check.isChecked()
        self.minimap_position_label.setEnabled(enabled and not custom_enabled)
        self.minimap_position_box.setEnabled(enabled and not custom_enabled)
        self.minimap_x_label.setEnabled(custom_enabled)
        self.minimap_x_box.setEnabled(custom_enabled)
        self.minimap_y_label.setEnabled(custom_enabled)
        self.minimap_y_box.setEnabled(custom_enabled)
        self.minimap_marker_shape_label.setEnabled(enabled)
        self.minimap_marker_shape_box.setEnabled(enabled)
        self.minimap_marker_color_label.setEnabled(enabled)
        self.minimap_marker_color_box.setEnabled(enabled)
        self.minimap_trail_color_label.setEnabled(enabled)
        self.minimap_trail_color_box.setEnabled(enabled)
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
        fields["overlay_line_spacing"] = int(self.overlay_line_spacing_box.value())
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
        fields["guide_enabled"] = bool(self.chk_guides.isChecked())
        fields["guide_offset"] = int(self.guide_offset_box.value())
        fields["guide_center_color"] = str(self.guide_center_color_box.currentText())
        fields["guide_side_color"] = str(self.guide_side_color_box.currentText())
        fields["guide_thickness"] = int(self.guide_thickness_box.value())
        fields["guide_dash_length"] = int(self.guide_dash_length_box.value())
        fields["guide_gap_length"] = int(self.guide_gap_length_box.value())
        fields["guide_length_pct"] = float(self.guide_length_pct_box.value())
        fields["guide_center_label"] = self.guide_center_label_box.text().strip()
        fields["guide_left_label"] = self.guide_left_label_box.text().strip()
        fields["guide_right_label"] = self.guide_right_label_box.text().strip()
        fields["guide_label_font_scale"] = float(self.guide_label_font_scale_box.value())
        fields["guide_label_thickness"] = int(self.guide_label_thickness_box.value())
        fields["banner_enabled"] = bool(self.chk_banner.isChecked())
        fields["banner_height"] = int(self.banner_height_box.value())
        fields["banner_color"] = str(self.banner_color_box.currentText())
        fields["banner_alpha"] = float(self.banner_alpha_box.value())
        fields["banner_border_color"] = str(self.banner_border_color_box.currentText())
        fields["banner_border_thickness"] = int(self.banner_border_thickness_box.value())
        fields["banner_texts"] = [
            {
                "enabled": bool(slot["enabled"].isChecked()),
                "text": slot["text"].text().strip(),
                "x": int(slot["x"].value()),
                "y": int(slot["y"].value()),
                "angle": float(slot["angle"].value()),
                "font_scale": float(slot["size"].value()),
                "font": str(slot["font"].currentText()),
                "color": str(slot["color"].currentText()),
            }
            for slot in self.banner_slots
            if slot["enabled"].isChecked() and slot["text"].text().strip()
        ]
        fields["minimap_enabled"] = bool(self.chk_minimap.isChecked())
        fields["minimap_zoom"] = int(self.minimap_zoom_box.value())
        fields["minimap_size"] = int(self.minimap_size_box.value())
        fields["minimap_position"] = str(self.minimap_position_box.currentText())
        fields["minimap_marker_shape"] = str(self.minimap_marker_shape_box.currentText())
        fields["minimap_marker_color"] = str(self.minimap_marker_color_box.currentText())
        fields["minimap_source"] = str(self.minimap_source_box.currentText())
        fields["minimap_trail_thickness"] = int(self.minimap_trail_thickness_box.value())
        fields["minimap_trail_color"] = str(self.minimap_trail_color_box.currentText())
        fields["minimap_custom_position"] = bool(self.minimap_custom_pos_check.isChecked())
        fields["minimap_x"] = int(self.minimap_x_box.value()) if self.minimap_custom_pos_check.isChecked() else None
        fields["minimap_y"] = int(self.minimap_y_box.value()) if self.minimap_custom_pos_check.isChecked() else None

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