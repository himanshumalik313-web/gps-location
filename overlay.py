import cv2

POSITIONS = {
    "top-left": lambda w, h, tw, th: (20, 20),
    "top-right": lambda w, h, tw, th: (w - tw - 20, 20),
    "bottom-left": lambda w, h, tw, th: (20, h - th - 20),
    "bottom-right": lambda w, h, tw, th: (w - tw - 20, h - th - 20),
}

class OverlayRenderer:
    def __init__(self, font_scale=0.6, color=(255, 255, 255), bg=True,
                 position="bottom-left", thickness=1, alpha=0.5):
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = font_scale
        self.color = color
        self.bg = bg
        self.position = position
        self.thickness = thickness
        self.alpha = float(alpha)

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
        line_height = 22
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