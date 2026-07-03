import cv2
from dataclasses import dataclass

@dataclass
class VideoInfo:
    fps: float
    frame_count: int
    width: int
    height: int
    duration: float

class VideoReader:
    """Opens the drone video and lets you loop through its frames one by one."""
    def __init__(self, path: str):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video: {path}")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.info = VideoInfo(
            fps=fps,
            frame_count=frame_count,
            width=int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            duration=frame_count / fps if fps else 0,
        )

    def frames(self):
        """Yield (frame_index, timestamp_seconds, frame_image) for every frame."""
        idx = 0
        while True:
            ok, frame = self.cap.read()
            if not ok:
                break
            timestamp = idx / self.info.fps
            yield idx, timestamp, frame
            idx += 1

    def release(self):
        self.cap.release()


class VideoWriter:
    """Builds the new output video, frame by frame."""
    def __init__(self, path: str, fps: float, width: int, height: int, codec="mp4v"):
        fourcc = cv2.VideoWriter_fourcc(*codec)
        self.writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
        if not self.writer.isOpened():
            raise IOError(f"Cannot open writer for: {path}")

    def write(self, frame):
        self.writer.write(frame)

    def release(self):
        self.writer.release()