import cv2
import numpy as np
import requests
import math
from collections import deque

# ── Tile helpers ──────────────────────────────────────────────────────────────

def _lat_lon_to_tile(lat, lon, zoom):
    """Convert GPS coordinates to OSM tile x/y numbers."""
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n)
    return x, y

def _lat_lon_to_global_pixel(lat, lon, zoom, tile_size=256):
    lat_r = math.radians(lat)
    n = 2 ** zoom
    px = (lon + 180) / 360 * n * tile_size
    py = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n * tile_size
    return px, py

def _tile_to_pixel_offset(lat, lon, zoom, tile_x, tile_y, tile_size=256):
    """Pixel offset of a GPS point within its tile."""
    lat_r = math.radians(lat)
    n = 2 ** zoom
    px = (lon + 180) / 360 * n * tile_size - tile_x * tile_size
    py = (1 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2 * n * tile_size - tile_y * tile_size
    return int(px), int(py)

def _fetch_tile(x, y, zoom, source="satellite"):
    """Download one tile as a numpy BGR image."""
    if source == "roadmap":
        url = f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png"
    else:
        url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{zoom}/{y}/{x}"
    headers = {"User-Agent": "DroneGeoTagger/1.0"}
    resp = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    arr = np.frombuffer(resp.content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

# ── Main minimap builder ───────────────────────────────────────────────────────

class MiniMapRenderer:
    """
    Builds a small map inset showing the drone's current position.
    Tiles are cached per zoom+tile so we don't re-download every frame.
    """

    def __init__(self, zoom=16, map_size=200, marker_color=(0, 0, 255), marker_shape="triangle",
                 trail_color=(0, 0, 255), trail_thickness=4, trail_length=30, source="satellite"):
        self.zoom = zoom          # higher = more zoomed in (16 is good for drone footage)
        self.map_size = map_size  # pixel size of the square inset box
        self.marker_color = marker_color
        self.marker_shape = marker_shape
        self.trail_color = trail_color
        self.trail_thickness = trail_thickness
        self.trail_length = trail_length
        self.source = source
        self._history = deque(maxlen=trail_length)
        self._tile_cache = {}
        self._map_cache = {}      # cache full stitched map per tile position

    def _get_tile(self, x, y):
        key = (x, y, self.zoom)
        if key not in self._tile_cache:
            try:
                self._tile_cache[key] = _fetch_tile(x, y, self.zoom, self.source)
            except Exception:
                if self.source == "satellite":
                    try:
                        self._tile_cache[key] = _fetch_tile(x, y, self.zoom, "roadmap")
                    except Exception:
                        # Return a grey placeholder if download fails
                        self._tile_cache[key] = np.full((256, 256, 3), 180, dtype=np.uint8)
                else:
                    self._tile_cache[key] = np.full((256, 256, 3), 180, dtype=np.uint8)
        return self._tile_cache[key]

    def _build_map_around(self, lat, lon):
        """
        Stitch a 3×3 grid of tiles centred on the drone's position,
        then crop to map_size × map_size centred on the drone.
        """
        cx, cy = _lat_lon_to_tile(lat, lon, self.zoom)
        cache_key = (cx, cy)
        if cache_key not in self._map_cache:
            rows = []
            for dy in range(-1, 2):
                cols = []
                for dx in range(-1, 2):
                    tile = self._get_tile(cx + dx, cy + dy)
                    cols.append(tile)
                rows.append(np.hstack(cols))
            stitched = np.vstack(rows)  # 768×768
            self._map_cache[cache_key] = (stitched, cx, cy)
        return self._map_cache[cache_key]

    def render(self, lat, lon, heading_deg=0) -> np.ndarray:
        """
        Returns a map_size × map_size BGR image with the drone position marked.
        heading_deg: drone's heading in degrees (0=North, 90=East, etc.)
        """
        self._history.append((lat, lon))
        stitched, tile_x, tile_y = self._build_map_around(lat, lon)

        # Pixel position of drone within the 3×3 stitched grid
        # The centre tile is at offset (256, 256) in the stitched image
        px, py = _tile_to_pixel_offset(lat, lon, self.zoom, tile_x - 1, tile_y - 1)
        origin_px = (tile_x - 1) * 256
        origin_py = (tile_y - 1) * 256

        # Crop map_size/2 around the drone's pixel position
        h, w = stitched.shape[:2]
        half = self.map_size // 2
        x1 = max(px - half, 0)
        y1 = max(py - half, 0)
        x2 = min(px + half, w)
        y2 = min(py + half, h)
        crop = stitched[y1:y2, x1:x2]

        # Pad if we hit the edge
        ph = self.map_size - crop.shape[0]
        pw = self.map_size - crop.shape[1]
        if ph > 0 or pw > 0:
            crop = np.pad(crop, ((0, ph), (0, pw), (0, 0)), constant_values=180)

        crop = crop.copy()

        # Draw recent path history as a red trail like the screenshot.
        trail_points = []
        for hlat, hlon in self._history:
            hpx, hpy = _lat_lon_to_global_pixel(hlat, hlon, self.zoom)
            rx = int(round(hpx - origin_px - x1))
            ry = int(round(hpy - origin_py - y1))
            if 0 <= rx < self.map_size and 0 <= ry < self.map_size:
                trail_points.append([rx, ry])
        if len(trail_points) >= 2:
            pts = np.array(trail_points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(crop, [pts], False, self.trail_color, int(self.trail_thickness), cv2.LINE_AA)

        # Centre of the cropped map = drone position
        mx = min(px - x1, self.map_size - 1)
        my = min(py - y1, self.map_size - 1)

        # Draw the current-position marker.
        marker_size = 10
        angle_rad = math.radians(heading_deg - 90)
        tip = (int(mx + marker_size * math.cos(angle_rad)), int(my + marker_size * math.sin(angle_rad)))
        left = (int(mx + marker_size * math.cos(angle_rad + 2.5)), int(my + marker_size * math.sin(angle_rad + 2.5)))
        right = (int(mx + marker_size * math.cos(angle_rad - 2.5)), int(my + marker_size * math.sin(angle_rad - 2.5)))
        tri = np.array([[tip, left, right]], dtype=np.int32)

        shape = str(self.marker_shape).lower()
        if shape == "circle":
            cv2.circle(crop, (mx, my), 6, self.marker_color, -1)
            cv2.circle(crop, (mx, my), 6, (255, 255, 255), 1)
        elif shape == "square":
            half = 6
            cv2.rectangle(crop, (mx - half, my - half), (mx + half, my + half), self.marker_color, -1)
            cv2.rectangle(crop, (mx - half, my - half), (mx + half, my + half), (255, 255, 255), 1)
        else:
            cv2.fillConvexPoly(crop, tri, self.marker_color)
            cv2.polylines(crop, tri, True, (0, 0, 0), 1, cv2.LINE_AA)

        # Draw border around the inset
        cv2.rectangle(crop, (0, 0), (self.map_size - 1, self.map_size - 1),
                      (255, 255, 255), 2)

        # Add coordinates text at the top of the inset.
        coord_text = f"+{lat:.5f} +{lon:.5f}"
        cv2.putText(crop, coord_text, (4, 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1, cv2.LINE_AA)

        return crop

    def paste_onto(self, frame, lat, lon, heading_deg=0,
                   position="top-right", margin=10):
        """
        Paste the mini-map inset onto a video frame.
        position: 'top-right', 'top-left', 'bottom-right', 'bottom-left'
        """
        inset = self.render(lat, lon, heading_deg)
        h, w = frame.shape[:2]
        s = self.map_size

        if position == "top-right":
            x, y = w - s - margin, margin
        elif position == "top-left":
            x, y = margin, margin
        elif position == "bottom-right":
            x, y = w - s - margin, h - s - margin
        else:
            x, y = margin, h - s - margin

        frame[y:y + s, x:x + s] = inset
        return frame