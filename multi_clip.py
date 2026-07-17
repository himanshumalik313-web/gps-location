"""
Handles multiple (video, gps/srt) clips as one continuous output.
Finds the best GPS-matched join point between consecutive clips so the
position/speed/heading overlay doesn't jump at the cut, and optionally
crossfades the video frames across the join to soften any visual gap.
"""

import numpy as np
from video_io import VideoReader
from gps_data import GPSData
from sync import synchronize


def _haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def find_best_join(sync_a, sync_b, search_window_sec=15.0, heading_weight_m_per_deg=2.0):
    """
    sync_a, sync_b: per-frame synced DataFrames (output of `synchronize`),
    indexed by frame_index, with Latitude/Longitude/Heading_deg/Time columns.

    Looks at the tail of clip A and the head of clip B, and returns
    (frame_a, frame_b) — the pair of frames whose GPS position (and heading)
    are closest to each other. Trim clip A after frame_a and clip B before
    frame_b to get the cleanest possible join.
    """
    tail = sync_a[sync_a["Time"] >= sync_a["Time"].max() - search_window_sec]
    head = sync_b[sync_b["Time"] <= sync_b["Time"].min() + search_window_sec]

    if tail.empty or head.empty:
        # Not enough data to search — just join at the very ends.
        return sync_a.index.max(), sync_b.index.min()

    best = None
    for fa, ra in tail.iterrows():
        dist = _haversine_m(ra["Latitude"], ra["Longitude"],
                             head["Latitude"].values, head["Longitude"].values)
        heading_diff = np.abs(((head["Heading_deg"].values - ra["Heading_deg"]) + 180) % 360 - 180)
        score = dist + heading_diff * heading_weight_m_per_deg
        j = int(np.argmin(score))
        if best is None or score[j] < best[0]:
            best = (score[j], fa, int(head.index[j]))

    _, frame_a, frame_b = best
    return frame_a, frame_b


class ClipPlan:
    """One entry in the multi-clip run: a video, its GPS sync table, and the
    frame range (after trimming) that actually gets written to output."""
    def __init__(self, video_path, gps_path, frame_interval=1):
        self.video_path = video_path
        self.reader = VideoReader(video_path)
        self.info = self.reader.info
        gps = GPSData.load(gps_path)
        self.sync_df = synchronize(gps, self.info, frame_interval).set_index("frame_index")
        self.start_frame = 0
        self.end_frame = self.sync_df.index.max()
        self.distance_offset = 0.0   # added to Total_Distance_m for continuity
        self.time_offset = 0.0       # added to Time for continuity


def build_plan(clip_specs, frame_interval=1, join_search_sec=15.0):
    """
    clip_specs: list of (video_path, gps_or_srt_path) in playback order.
    Returns a list of ClipPlan with trim points and cumulative offsets set.
    """
    plans = [ClipPlan(v, g, frame_interval) for v, g in clip_specs]

    running_distance = 0.0
    running_time = 0.0
    for i, plan in enumerate(plans):
        plan.time_offset = running_time
        plan.distance_offset = running_distance

        if i < len(plans) - 1:
            nxt = plans[i + 1]
            fa, fb = find_best_join(plan.sync_df, nxt.sync_df, join_search_sec)
            plan.end_frame = fa
            nxt.start_frame = fb

        # accumulate distance/time only over the *kept* portion of this clip
        kept = plan.sync_df.loc[plan.start_frame:plan.end_frame]
        if "Total_Distance_m" in kept.columns and len(kept):
            running_distance += kept["Total_Distance_m"].iloc[-1] - kept["Total_Distance_m"].iloc[0]
        if len(kept):
            running_time += kept["Time"].iloc[-1] - kept["Time"].iloc[0]

    return plans