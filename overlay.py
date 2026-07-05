import cv2
import numpy as np

NAMED_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (0, 0, 255),
    "green": (0, 255, 0),
    "blue": (255, 0, 0),
    "yellow": (0, 255, 255),
    "orange": (0, 165, 255),
    "cyan": (255, 255, 0),
    "magenta": (255, 0, 255),
    "gray": (128, 128, 128),
}

FONT_STYLES = {
    "simplex": cv2.FONT_HERSHEY_SIMPLEX,
    "plain": cv2.FONT_HERSHEY_PLAIN,
    "duplex": cv2.FONT_HERSHEY_DUPLEX,
    "complex": cv2.FONT_HERSHEY_COMPLEX,
    "triplex": cv2.FONT_HERSHEY_TRIPLEX,
    "complex_small": cv2.FONT_HERSHEY_COMPLEX_SMALL,
    "script_simplex": cv2.FONT_HERSHEY_SCRIPT_SIMPLEX,
    "script_complex": cv2.FONT_HERSHEY_SCRIPT_COMPLEX,
}


def resolve_color(value, default=(255, 255, 255)):
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return tuple(int(max(0, min(255, channel))) for channel in value)
    if isinstance(value, str):
        return NAMED_COLORS.get(value.lower(), default)
    return default


def resolve_font(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return FONT_STYLES.get(value.lower(), cv2.FONT_HERSHEY_SIMPLEX)
    return cv2.FONT_HERSHEY_SIMPLEX


def draw_rotated_text(frame, text, x, y, font_scale=0.6, color=(255, 255, 255), angle_deg=0,
                      thickness=1, font=cv2.FONT_HERSHEY_SIMPLEX):
    if not text:
        return frame

    font_id = resolve_font(font)
    color_bgr = resolve_color(color)
    (text_w, text_h), baseline = cv2.getTextSize(text, font_id, font_scale, thickness)
    pad = max(6, int(round(max(1.0, font_scale * 12))))
    canvas_h = text_h + baseline + pad * 2
    canvas_w = text_w + pad * 2
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    cv2.putText(canvas, text, (pad, pad + text_h), font_id, font_scale, color_bgr, thickness, cv2.LINE_AA)

    if angle_deg:
        matrix = cv2.getRotationMatrix2D((canvas_w / 2.0, canvas_h / 2.0), angle_deg, 1.0)
        rendered = cv2.warpAffine(
            canvas,
            matrix,
            (canvas_w, canvas_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
    else:
        rendered = canvas

    frame_h, frame_w = frame.shape[:2]
    render_h, render_w = rendered.shape[:2]
    x0 = int(round(x - render_w / 2.0))
    y0 = int(round(y - render_h / 2.0))
    x1 = max(0, x0)
    y1 = max(0, y0)
    x2 = min(frame_w, x0 + render_w)
    y2 = min(frame_h, y0 + render_h)
    if x1 >= x2 or y1 >= y2:
        return frame

    src_x1 = x1 - x0
    src_y1 = y1 - y0
    src_x2 = src_x1 + (x2 - x1)
    src_y2 = src_y1 + (y2 - y1)
    src = rendered[src_y1:src_y2, src_x1:src_x2]
    dst = frame[y1:y2, x1:x2]
    mask = np.any(src > 0, axis=2)
    dst[mask] = src[mask]
    return frame


def _dashed_vline(frame, x, y1, y2, color, thickness, dash_len=18, gap_len=14):
    y = y1
    while y < y2:
        y_end = min(y + dash_len, y2)
        cv2.line(frame, (x, y), (x, y_end), resolve_color(color), thickness, cv2.LINE_AA)
        y += dash_len + gap_len
    return frame


def draw_guides(frame, offset_x=150, cl_color=(0, 220, 255), row_color=(220, 220, 220),
                thickness=3, dash_length=18, gap_length=14, length_pct=0.85,
                cl_label="CL", left_label="LEFT", right_label="RIGHT",
                label_font_scale=0.7, label_thickness=1):
    h, w = frame.shape[:2]
    cx = w // 2
    y1 = int(h * (1 - float(length_pct)) / 2)
    y2 = h - y1

    _dashed_vline(frame, cx, y1, y2, cl_color, thickness, dash_length, gap_length)
    _dashed_vline(frame, cx - int(offset_x), y1, y2, row_color, thickness, dash_length, gap_length)
    _dashed_vline(frame, cx + int(offset_x), y1, y2, row_color, thickness, dash_length, gap_length)

    mid_y = (y1 + y2) // 2
    draw_rotated_text(frame, cl_label, cx, mid_y, font_scale=label_font_scale,
                      color=cl_color, angle_deg=90, thickness=label_thickness)
    draw_rotated_text(frame, left_label, cx - int(offset_x), mid_y, font_scale=label_font_scale,
                      color=row_color, angle_deg=90, thickness=label_thickness)
    draw_rotated_text(frame, right_label, cx + int(offset_x), mid_y, font_scale=label_font_scale,
                      color=row_color, angle_deg=90, thickness=label_thickness)
    return frame


def draw_border_banner(frame, height=72, color=(0, 0, 0), alpha=0.45, texts=None,
                       border_color=(255, 255, 255), border_thickness=1):
    h, w = frame.shape[:2]
    banner_h = max(0, min(int(height), h))
    if banner_h <= 0:
        return frame

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w - 1, banner_h - 1), resolve_color(color), -1)
    frame = cv2.addWeighted(overlay, max(0.0, min(1.0, float(alpha))), frame,
                            1.0 - max(0.0, min(1.0, float(alpha))), 0)
    cv2.rectangle(frame, (0, 0), (w - 1, banner_h - 1), resolve_color(border_color), int(border_thickness), cv2.LINE_AA)

    for spec in texts or []:
        if not spec or not spec.get("enabled", True):
            continue
        text = str(spec.get("text", "")).strip()
        if not text:
            continue
        draw_rotated_text(
            frame,
            text,
            int(spec.get("x", w // 2)),
            int(spec.get("y", banner_h // 2)),
            font_scale=float(spec.get("font_scale", 0.6)),
            color=spec.get("color", (255, 255, 255)),
            angle_deg=float(spec.get("angle", 0)),
            thickness=int(spec.get("thickness", 1)),
            font=spec.get("font", cv2.FONT_HERSHEY_SIMPLEX),
        )
    return frame

POSITIONS = {
    "top-left": lambda w, h, tw, th: (20, 20),
    "top-right": lambda w, h, tw, th: (w - tw - 20, 20),
    "bottom-left": lambda w, h, tw, th: (20, h - th - 20),
    "bottom-right": lambda w, h, tw, th: (w - tw - 20, h - th - 20),
}

class OverlayRenderer:
    def __init__(self, font_scale=0.6, color=(255, 255, 255), bg=True,
                 position="bottom-left", thickness=1, alpha=0.5, line_spacing=0):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = font_scale
        self.color = color
        self.bg = bg
        self.position = position
        self.thickness = thickness
        self.alpha = float(alpha)
        self.line_spacing = int(line_spacing)

    def build_lines(self, row, fields: dict, place: dict | None):
        lines = []
        if fields.get("latitude"):
            lines.append(f"Lat: {row['Latitude']:.6f}")
        if fields.get("longitude"):
            lines.append(f"Lon: {row['Longitude']:.6f}")
        if fields.get("altitude"):
            lines.append(f"Alt: {row['Altitude']:.1f} m")
        if fields.get("speed"):
            lines.append(f"Speed: {row['Speed_mps']:.1f} m/s")
        if fields.get("heading"):
            lines.append(f"Heading: {row['Heading_deg']:.0f}°")
        if fields.get("timestamp"):
            t = row["Time"]
            lines.append(f"Time: {int(t//60):02d}:{int(t%60):02d}")
        if fields.get("place") and place:
            lines.append(f"{place.get('city','')}, {place.get('state','')}, {place.get('country','')}")
        if fields.get("distance") and "Total_Distance_m" in row:
            lines.append(f"Dist: {row['Distance_m']:.1f} m")
        if fields.get("distance_km") and "Total_Distance_km" in row:
            lines.append(f"Total: {row['Total_Distance_km']:.3f} km")
        # Optional source info (video/gps filenames) that can be supplied via fields
        if fields.get("show_src_info"):
            video_name = fields.get("video_name")
            gps_name = fields.get("gps_name")
            if video_name:
                lines.append(f"Video: {video_name}")
            if gps_name:
                lines.append(f"GPS: {gps_name}")
        return lines

    def draw(self, frame, lines):
        h, w = frame.shape[:2]
        line_height = 22 + max(0, int(self.line_spacing))
        sizes = [cv2.getTextSize(l, self.font, self.font_scale, self.thickness)[0] for l in lines]
        tw = max((s[0] for s in sizes), default=0)
        th = line_height * len(lines)
        x, y = POSITIONS.get(self.position, POSITIONS["bottom-left"])(w, h, tw, th)

        if self.bg:
            overlay = frame.copy()
            cv2.rectangle(overlay, (x - 10, y - 10), (x + tw + 10, y + th + 10), (0, 0, 0), -1)
            a = max(0.0, min(1.0, float(self.alpha)))
            frame = cv2.addWeighted(overlay, a, frame, 1.0 - a, 0)

        for i, line in enumerate(lines):
            cv2.putText(frame, line, (x, y + (i + 1) * line_height - 6),
                        self.font, self.font_scale, self.color, self.thickness, cv2.LINE_AA)
        return frame