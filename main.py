import os
from video_io import VideoReader, VideoWriter
from gps_data import GPSData
from sync import synchronize
from overlay import OverlayRenderer, draw_border_banner, draw_guides, resolve_color
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
    "bold": False,
    "boldness": 2,
    "overlay_line_spacing": 0,
    "alpha": 0.5,
    "show_src_info": False,
    "guide_enabled": True,
    "guide_offset": 150,
    "guide_center_color": "yellow",
    "guide_side_color": "white",
    "guide_thickness": 3,
    "guide_dash_length": 18,
    "guide_gap_length": 14,
    "guide_length_pct": 0.85,
    "guide_center_label": "CL",
    "guide_left_label": "LEFT",
    "guide_right_label": "RIGHT",
    "guide_label_font_scale": 0.7,
    "guide_label_thickness": 1,
    "banner_enabled": False,
    "banner_height": 72,
    "banner_color": "black",
    "banner_alpha": 0.45,
    "banner_border_color": "white",
    "banner_border_thickness": 1,
    "banner_texts": [],
    "minimap_enabled": False,
    "minimap_zoom": 16,
    "minimap_size": 200,
    "minimap_position": "top-right",
    "minimap_custom_position": False,
    "minimap_x": None,
    "minimap_y": None,
    "minimap_marker_shape": "triangle",
    "minimap_marker_color": "red",
    "minimap_trail_thickness": 4,
    "minimap_trail_color": "red",
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
        line_spacing=fields.get("overlay_line_spacing", 0),
        bold=fields.get("bold", False),
        boldness=int(fields.get("boldness", 2)),
    )
    minimap = MiniMapRenderer(
        zoom=int(fields.get("minimap_zoom", 16)),
        map_size=int(fields.get("minimap_size", 200)),
        marker_shape=fields.get("minimap_marker_shape", "triangle"),
        marker_color=_MINIMAP_COLOR_MAP.get(fields.get("minimap_marker_color", "red"), (0, 0, 255)),
        trail_thickness=int(fields.get("minimap_trail_thickness", 4)),
        trail_color=_MINIMAP_COLOR_MAP.get(fields.get("minimap_trail_color", "red"), (0, 0, 255)),
        source=fields.get("minimap_source", "satellite"),
    ) if fields.get("minimap_enabled") else None
    place_cache = {}

    for idx, ts, frame in reader.frames():
        if fields.get("guide_enabled"):
            frame = draw_guides(
                frame,
                offset_x=int(fields.get("guide_offset", 150)),
                cl_color=resolve_color(fields.get("guide_center_color", "yellow")),
                row_color=resolve_color(fields.get("guide_side_color", "white")),
                thickness=int(fields.get("guide_thickness", 3)),
                dash_length=int(fields.get("guide_dash_length", 18)),
                gap_length=int(fields.get("guide_gap_length", 14)),
                length_pct=float(fields.get("guide_length_pct", 0.85)),
                cl_label=str(fields.get("guide_center_label", "CL")),
                left_label=str(fields.get("guide_left_label", "LEFT")),
                right_label=str(fields.get("guide_right_label", "RIGHT")),
                label_font_scale=float(fields.get("guide_label_font_scale", 0.7)),
                label_thickness=int(fields.get("guide_label_thickness", 1)),
            )

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
                minimap_x = fields.get("minimap_x")
                minimap_y = fields.get("minimap_y")
                frame = minimap.paste_onto(
                    frame,
                    lat=row["Latitude"],
                    lon=row["Longitude"],
                    heading_deg=row.get("Heading_deg", 0),
                    position=fields.get("minimap_position", "top-right"),
                    margin=10,
                    x=int(minimap_x) if minimap_x is not None else None,
                    y=int(minimap_y) if minimap_y is not None else None,
                )

        if fields.get("banner_enabled"):
            frame = draw_border_banner(
                frame,
                height=int(fields.get("banner_height", 72)),
                color=resolve_color(fields.get("banner_color", "black")),
                alpha=float(fields.get("banner_alpha", 0.45)),
                border_color=resolve_color(fields.get("banner_border_color", "white")),
                border_thickness=int(fields.get("banner_border_thickness", 1)),
                texts=fields.get("banner_texts", []),
            )

        writer.write(frame)

        if progress_callback and idx % 30 == 0:
            progress_callback(idx, info.frame_count)

    reader.release()
    writer.release()


def run_multi(clip_specs, output_path, fields, frame_interval=1, join_search_sec=15.0,
              crossfade_frames=6, progress_callback=None):
    """
    clip_specs: ordered list of (video_path, gps_or_srt_path).
    Joins all clips into one output video, using GPS to pick the best cut
    point between consecutive clips (minimizing position/heading jump),
    and optionally crossfading `crossfade_frames` frames across each join
    to soften any remaining visual discontinuity.
    """
    from multi_clip import build_plan

    plans = build_plan(clip_specs, frame_interval, join_search_sec)
    first_info = plans[0].info
    writer = VideoWriter(output_path, first_info.fps, first_info.width, first_info.height)

    overlay = OverlayRenderer(
        font_scale=fields.get("font_scale", 0.6),
        position=fields.get("position", "bottom-left"),
        alpha=fields.get("alpha", 0.5),
        line_spacing=fields.get("overlay_line_spacing", 0),
        bold=fields.get("bold", False),
        boldness=int(fields.get("boldness", 2)),
    )
    minimap = MiniMapRenderer(
        zoom=int(fields.get("minimap_zoom", 16)),
        map_size=int(fields.get("minimap_size", 200)),
        marker_shape=fields.get("minimap_marker_shape", "triangle"),
        marker_color=_MINIMAP_COLOR_MAP.get(fields.get("minimap_marker_color", "red"), (0, 0, 255)),
        trail_thickness=int(fields.get("minimap_trail_thickness", 4)),
        trail_color=_MINIMAP_COLOR_MAP.get(fields.get("minimap_trail_color", "red"), (0, 0, 255)),
        source=fields.get("minimap_source", "satellite"),
    ) if fields.get("minimap_enabled") else None

    place_cache = {}
    total_frames_all = sum(p.end_frame - p.start_frame + 1 for p in plans)
    frames_done = 0
    prev_tail_frames = []  # buffered last frames of previous clip, for crossfade

    import cv2

    for clip_idx, plan in enumerate(plans):
        w, h = first_info.width, first_info.height
        idx = 0
        buffered = []  # ring buffer of upcoming frames so we can crossfade at the tail
        for frame_idx, ts, frame in plan.reader.frames():
            if frame_idx < plan.start_frame:
                continue
            if frame_idx > plan.end_frame:
                break
            if frame.shape[1] != w or frame.shape[0] != h:
                frame = cv2.resize(frame, (w, h))

            if fields.get("guide_enabled"):
                frame = draw_guides(
                    frame,
                    offset_x=int(fields.get("guide_offset", 150)),
                    cl_color=resolve_color(fields.get("guide_center_color", "yellow")),
                    row_color=resolve_color(fields.get("guide_side_color", "white")),
                    thickness=int(fields.get("guide_thickness", 3)),
                    dash_length=int(fields.get("guide_dash_length", 18)),
                    gap_length=int(fields.get("guide_gap_length", 14)),
                    length_pct=float(fields.get("guide_length_pct", 0.85)),
                    cl_label=str(fields.get("guide_center_label", "CL")),
                    left_label=str(fields.get("guide_left_label", "LEFT")),
                    right_label=str(fields.get("guide_right_label", "RIGHT")),
                    label_font_scale=float(fields.get("guide_label_font_scale", 0.7)),
                    label_thickness=int(fields.get("guide_label_thickness", 1)),
                )

            row = None
            if frame_idx in plan.sync_df.index:
                row = plan.sync_df.loc[frame_idx].copy()
                row["Time"] = row["Time"] + plan.time_offset
                if "Total_Distance_m" in row:
                    row["Total_Distance_m"] = row["Total_Distance_m"] + plan.distance_offset
                    row["Total_Distance_km"] = row["Total_Distance_m"] / 1000

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
                    minimap_x = fields.get("minimap_x")
                    minimap_y = fields.get("minimap_y")
                    frame = minimap.paste_onto(
                        frame,
                        lat=row["Latitude"],
                        lon=row["Longitude"],
                        heading_deg=row.get("Heading_deg", 0),
                        position=fields.get("minimap_position", "top-right"),
                        margin=10,
                        x=int(minimap_x) if minimap_x is not None else None,
                        y=int(minimap_y) if minimap_y is not None else None,
                    )

            if fields.get("banner_enabled"):
                frame = draw_border_banner(
                    frame,
                    height=int(fields.get("banner_height", 72)),
                    color=resolve_color(fields.get("banner_color", "black")),
                    alpha=float(fields.get("banner_alpha", 0.45)),
                    border_color=resolve_color(fields.get("banner_border_color", "white")),
                    border_thickness=int(fields.get("banner_border_thickness", 1)),
                    texts=fields.get("banner_texts", []),
                )

            # Crossfade: blend the first `crossfade_frames` of this clip
            # with the buffered last frames of the previous clip.
            if clip_idx > 0 and idx < crossfade_frames and idx < len(prev_tail_frames):
                alpha = (idx + 1) / (crossfade_frames + 1)
                frame = cv2.addWeighted(prev_tail_frames[idx], 1 - alpha, frame, alpha, 0)

            writer.write(frame)
            buffered.append(frame)
            if len(buffered) > crossfade_frames:
                buffered.pop(0)

            idx += 1
            frames_done += 1
            if progress_callback and frames_done % 30 == 0:
                progress_callback(frames_done, total_frames_all)

        prev_tail_frames = buffered
        plan.reader.release()

    writer.release()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", action="append", required=True,
                         help="Drone video. Repeat --video/--gps in matching order for multiple clips.")
    parser.add_argument("--gps", action="append", default=None,
                         help="GPS/SRT file matching each --video, same order.")
    parser.add_argument("--join-search-sec", type=float, default=15.0,
                         help="Seconds to search at each clip boundary for the best GPS-matched join.")
    parser.add_argument("--crossfade-frames", type=int, default=6,
                         help="Frames to crossfade across each clip join.")
    parser.add_argument("--output", default="output_geotagged.mp4")
    parser.add_argument("--font-scale", type=float, default=0.6)
    parser.add_argument("--bold", action="store_true", help="Render overlay text with extra stroke thickness")
    parser.add_argument("--boldness", type=int, default=2, help="Extra stroke thickness used when bold is enabled")
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
    fields["bold"] = bool(args.bold)
    fields["boldness"] = int(args.boldness)
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

    if len(args.video) > 1:
        gps_list = args.gps or []
        if len(gps_list) != len(args.video):
            raise ValueError("Provide one --gps/--srt per --video, in matching order.")
        clip_specs = list(zip(args.video, gps_list))
        run_multi(clip_specs, args.output, fields,
                  join_search_sec=args.join_search_sec,
                  crossfade_frames=args.crossfade_frames)
    else:
        gps_path = args.gps[0] if args.gps else None
        run(args.video[0], gps_path, args.output, fields)
    print(f"Done. Saved to {args.output}")