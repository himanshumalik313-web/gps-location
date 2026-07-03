import pandas as pd
import numpy as np
import os
import re

REQUIRED_COLUMNS = [ "Latitude", "Longitude"]

class GPSData:
    def __init__(self, df: pd.DataFrame):
        self.df = df.sort_values("Time").reset_index(drop=True)
        self._validate()

    def _validate(self):
        for col in REQUIRED_COLUMNS:
            if col not in self.df.columns:
                raise ValueError(f"Missing required column: {col}")
        if "Altitude" not in self.df.columns:
            self.df["Altitude"] = np.nan
        self.df = self.df.dropna(subset=["Time"])

    @classmethod
    def load(cls, path: str) -> "GPSData":
        ext = os.path.splitext(path)[1].lower()
        if ext == ".srt":
            return cls(_parse_dji_srt(path))
        elif ext == ".csv":
            df = pd.read_csv(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif ext == ".json":
            df = pd.read_json(path)
        elif ext == ".txt":
            df = pd.read_csv(path, sep='\s+')
        else:
            raise ValueError(f"Unsupported GPS file format: {ext}")
        return cls(df)

    def interpolate(self, target_times: np.ndarray) -> pd.DataFrame:
        t = self.df["Time"].values
        out = pd.DataFrame({"Time": target_times})
        for col in ["Latitude", "Longitude", "Altitude"]:
            vals = self.df[col].values
            out[col] = np.interp(target_times, t, vals,
                                  left=vals[0], right=vals[-1])
        return out

    def estimate_speed_heading(self, df: pd.DataFrame) -> pd.DataFrame:
        lat = np.radians(df["Latitude"].values)
        lon = np.radians(df["Longitude"].values)
        dt = np.diff(df["Time"].values, prepend=df["Time"].values[0])
        dt[dt == 0] = 1e-6
        dlat = np.diff(lat, prepend=lat[0])
        dlon = np.diff(lon, prepend=lon[0])
        R = 6371000
        x = dlon * np.cos(lat)
        y = dlat
        dist = R * np.sqrt(x**2 + y**2)
        df["Speed_mps"] = dist / dt
        df["Heading_deg"] = (np.degrees(np.arctan2(x, y)) + 360) % 360
        return df


def _parse_dji_srt(path: str) -> pd.DataFrame:
    """
    Parse a DJI-generated .SRT subtitle file into a GPS DataFrame.
    DJI SRT format per block:
        <index>
        HH:MM:SS,mmm --> HH:MM:SS,mmm
        <i><u>F/x.x, SS xxx, ISO xxx, EV x,
              GPS (lon, lat, satellites), D xm, H xm, H.S xm/s, V.S xm/s
        </i></u>
    Note: DJI stores GPS as (Longitude, Latitude) — not the usual order!
    """
    records = []

    # Read entire file
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Split into subtitle blocks (separated by blank lines)
    blocks = re.split(r'\n\s*\n', content.strip())

    time_pattern = re.compile(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->'
    )
    gps_pattern = re.compile(
        r'GPS\s*\(\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*\)'
    )
    alt_pattern = re.compile(r'H\s+([\d.\-]+)m')
    hspeed_pattern = re.compile(r'H\.S\s+([\d.\-]+)m/s')
    vspeed_pattern = re.compile(r'V\.S\s+([\d.\-]+)m/s')

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue

        # Parse timestamp from line 2
        t_match = time_pattern.search(lines[1])
        if not t_match:
            continue
        h, m, s, ms = map(int, t_match.groups())
        time_sec = h * 3600 + m * 60 + s + ms / 1000.0

        # Parse GPS data from remaining lines joined together
        data_line = " ".join(lines[2:])

        gps_match = gps_pattern.search(data_line)
        if not gps_match:
            continue

        # DJI format: GPS(longitude, latitude, satellite_count)
        lon = float(gps_match.group(1))
        lat = float(gps_match.group(2))
        # group(3) is satellite count, not altitude — skip it

        alt_match = alt_pattern.search(data_line)
        altitude = float(alt_match.group(1)) if alt_match else 0.0

        records.append({
            "Latitude": lat,
            "Longitude": lon
        })

    if not records:
        raise ValueError("No GPS data found in SRT file.")

    return pd.DataFrame(records)