import pandas as pd
import numpy as np
import os
import re

REQUIRED_COLUMNS = ["Time", "Latitude", "Longitude"]

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
        """Reads CSV, Excel, JSON, or TXT and returns a unified GPSData object."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".srt":
            df = _parse_dji_srt(path)
        elif ext == ".csv":
            df = pd.read_csv(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif ext == ".json":
            df = pd.read_json(path)
        elif ext == ".txt":
            df = pd.read_csv(path, delim_whitespace=True)
        else:
            raise ValueError(f"Unsupported GPS file format: {ext}")
        return cls(df)

    def interpolate(self, target_times: np.ndarray) -> pd.DataFrame:
        """Estimate lat/lon/altitude at any timestamp, filling gaps in the log."""
        t = self.df["Time"].values
        out = pd.DataFrame({"Time": target_times})
        for col in ["Latitude", "Longitude", "Altitude"]:
            vals = self.df[col].values
            out[col] = np.interp(target_times, t, vals, left=vals[0], right=vals[-1])
        return out

    def estimate_speed_heading(self, df: pd.DataFrame) -> pd.DataFrame:
        """Roughly computes speed (m/s) and heading (degrees) between consecutive points."""
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

    def calculate_distance_covered(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate per-step and cumulative distance from speed or GPS coordinates."""
        if "Speed_mps" in df.columns:
            dt = df["Time"].diff().fillna(1.0)
            df["Distance_m"] = df["Speed_mps"] * dt
            df["Distance_km"] = df["Distance_m"] / 1000
            df["Total_Distance_m"] = df["Distance_m"].cumsum()
            df["Total_Distance_km"] = df["Total_Distance_m"] / 1000
        else:
            lat = np.radians(df["Latitude"].values)
            lon = np.radians(df["Longitude"].values)
            dlat = np.diff(lat, prepend=lat[0])
            dlon = np.diff(lon, prepend=lon[0])
            R = 6371000
            a = np.sin(dlat / 2) ** 2 + np.cos(lat) * np.cos(lat) * np.sin(dlon / 2) ** 2
            dist = R * 2 * np.arcsin(np.sqrt(a))
            df["Distance_m"] = dist
            df["Distance_km"] = dist / 1000
            df["Total_Distance_m"] = np.cumsum(dist)
            df["Total_Distance_km"] = df["Total_Distance_m"] / 1000
        return df


def _parse_dji_srt(path: str) -> pd.DataFrame:
    """Parse a DJI-generated .SRT subtitle file into a GPS DataFrame."""
    records = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n', content.strip())
    time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->')
    gps_pattern = re.compile(r'GPS\s*\(\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*,\s*([\d.\-]+)\s*\)')
    alt_pattern = re.compile(r'H\s+([\d.\-]+)m')

    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue

        t_match = time_pattern.search(lines[1])
        if not t_match:
            continue
        h, m, s, ms = map(int, t_match.groups())
        time_sec = h * 3600 + m * 60 + s + ms / 1000.0

        data_line = " ".join(lines[2:])
        gps_match = gps_pattern.search(data_line)
        if not gps_match:
            continue

        lon = float(gps_match.group(1))
        lat = float(gps_match.group(2))
        alt_match = alt_pattern.search(data_line)
        altitude = float(alt_match.group(1)) if alt_match else 0.0

        records.append({
            "Time": time_sec,
            "Latitude": lat,
            "Longitude": lon,
            "Altitude": altitude,
        })

    if not records:
        raise ValueError("No GPS data found in SRT file.")

    return pd.DataFrame(records)