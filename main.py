import os
from video_io import VideoReader, VideoWriter
from gps_data import GPSData
from sync import synchronize
from overlay import OverlayRenderer
from geocode import reverse_geocode
from minimap import MiniMapRenderer
import ai_localize

DEFAULT_FIELDS = {
    "latitude": True,
    "longitude": True,
    "altitude": False,
    "speed": False,
    "heading": False,
    "timestamp": False,
    "place": False,
    "font_scale": 0.6,
    "alpha": 0.5,
    "show_src_info": False,
    "minimap_enabled": False,
    "minimap_zoom": 16,
    "minimap_size": 200,
    "minimap_position": "top-right",
    "minimap_marker_shape": "triangle",
    "minimap_marker_color": "red",
    "minimap_trail_thickness": 4,
    "minimap_source": "satellite",
    "position": "bottom-left",
    "distance": False,
    "distance_km": False,
    "distance_enabled": False,
}

_MINIMAP_COLOR_MAP = {
    "red": (0, 0, 255),
    "yellow": (0, 255, 255),
    "white": (255, 255, 255),
    "green": (0, 255, 0),
    "blue": (255, 0, 0),
    "orange": (0, 165, 255),
}

def run(video_path, gps_path, output_path, fields, frame_interval=1, enable_ai=False, progress_callback=None):
    reader = VideoReader(video_path)
    info = reader.info
    writer = VideoWriter(output_path, info.fps, info.width, info.height)

    sync_df = None
    if gps_path:
        gps = GPSData.load(gps_path)
        sync_df = synchronize(gps, info, frame_interval)
        sync_df = sync_df.set_index("frame_index")

    overlay = OverlayRenderer(
        font_scale=fields.get("font_scale", 0.6),
        position=fields.get("position", "bottom-left"),
        alpha=fields.get("alpha", 0.5),
    )
    minimap = MiniMapRenderer(
        zoom=int(fields.get("minimap_zoom", 16)),
        map_size=int(fields.get("minimap_size", 200)),
        marker_shape=fields.get("minimap_marker_shape", "triangle"),
        marker_color=_MINIMAP_COLOR_MAP.get(fields.get("minimap_marker_color", "red"), (0, 0, 255)),
        trail_thickness=int(fields.get("minimap_trail_thickness", 4)),
        source=fields.get("minimap_source", "satellite"),
    ) if fields.get("minimap_enabled") else None
    place_cache = {}

    for idx, ts, frame in reader.frames():
        row = None
        if sync_df is not None and idx in sync_df.index:
            row = sync_df.loc[idx]
        elif enable_ai:
            loc = ai_localize.estimate_location(frame)
            if loc:
                lat, lon = loc
                row = {"Latitude": lat, "Longitude": lon, "Altitude": 0,
                       "Speed_mps": 0, "Heading_deg": 0, "Time": ts}

        if row is not None:
            place = None
            if fields.get("place"):
                key = (round(row["Latitude"], 3), round(row["Longitude"], 3))
                if key not in place_cache:
                    place_cache[key] = reverse_geocode(row["Latitude"], row["Longitude"])
                place = place_cache[key]

            lines = overlay.build_lines(row, fields, place)
            frame = overlay.draw(frame, lines)

            if minimap is not None:
                frame = minimap.paste_onto(
                    frame,
                    lat=row["Latitude"],
                    lon=row["Longitude"],
                    heading_deg=row.get("Heading_deg", 0),
                    position=fields.get("minimap_position", "top-right"),
                    margin=10,
                )

        writer.write(frame)

        if progress_callback and idx % 30 == 0:
            progress_callback(idx, info.frame_count)

    reader.release()
    writer.release()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--gps", default=None)
    parser.add_argument("--output", default="output_geotagged.mp4")
    parser.add_argument("--font-scale", type=float, default=0.6)
    parser.add_argument("--alpha", type=float, default=0.5, help="Overlay background alpha (0.0-1.0)")
    parser.add_argument("--show-src-info", action="store_true", help="Show source file names in overlay")
    parser.add_argument("--minimap", action="store_true", help="Show minimap inset")
    parser.add_argument("--show-distance", action="store_true", help="Show distance in meters")
    parser.add_argument("--show-distance-km", action="store_true", help="Show total distance in kilometers")
    parser.add_argument("--minimap-zoom", type=int, default=16, help="Minimap zoom level")
    parser.add_argument("--minimap-size", type=int, default=200, help="Minimap square size in pixels")
    parser.add_argument("--minimap-position", default="top-right", choices=["top-left", "top-right", "bottom-left", "bottom-right"])
    parser.add_argument("--minimap-marker-shape", default="triangle", choices=["triangle", "circle", "square"])
    parser.add_argument("--minimap-marker-color", default="red", choices=list(_MINIMAP_COLOR_MAP.keys()))
    parser.add_argument("--minimap-trail-thickness", type=int, default=4, help="Minimap trail thickness")
    parser.add_argument("--minimap-source", default="satellite", choices=["satellite", "roadmap"], help="Minimap map source")
    args = parser.parse_args()

    fields = DEFAULT_FIELDS.copy()
    fields["font_scale"] = args.font_scale
    fields["alpha"] = args.alpha
    fields["show_src_info"] = bool(args.show_src_info)
    fields["minimap_enabled"] = bool(args.minimap)
    fields["minimap_zoom"] = int(args.minimap_zoom)
    fields["minimap_size"] = int(args.minimap_size)
    fields["minimap_position"] = args.minimap_position
    fields["minimap_marker_shape"] = args.minimap_marker_shape
    fields["minimap_marker_color"] = args.minimap_marker_color
    fields["minimap_trail_thickness"] = int(args.minimap_trail_thickness)
    fields["minimap_source"] = args.minimap_source
    fields["distance"] = bool(args.show_distance)
    fields["distance_km"] = bool(args.show_distance_km)
    fields["distance_enabled"] = bool(args.show_distance or args.show_distance_km)
    run(args.video, args.gps, args.output, fields)
    print(f"Done. Saved to {args.output}")