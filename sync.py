import numpy as np
from gps_data import GPSData

def build_frame_timeline(video_info, frame_interval: int = 1) -> np.ndarray:
    """List of timestamps for the frames we'll tag (every Nth frame if interval > 1)."""
    indices = np.arange(0, video_info.frame_count, frame_interval)
    return indices / video_info.fps

def synchronize(gps: GPSData, video_info, frame_interval: int = 1):
    """Returns a table: for every frame index, what GPS data applies."""
    timeline = build_frame_timeline(video_info, frame_interval)
    df = gps.interpolate(timeline)
    df = gps.estimate_speed_heading(df)
    df = gps.calculate_distance_covered(df)   # ← add this line
    df["frame_index"] = (df["Time"] * video_info.fps).round().astype(int)
    return df