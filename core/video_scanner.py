from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import exifread
from natsort import natsorted
from PIL import Image
from PyQt6.QtGui import QPixmap, QImage


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mts", ".m2ts", ".mkv"}
THUMBNAIL_DIR = Path(__file__).parent.parent / "assets" / "thumbnails"


@dataclass
class VideoClip:
    path: Path
    name: str
    duration: float          # seconds
    creation_date: datetime
    file_size: int           # bytes
    thumbnail_path: Optional[Path]
    order_index: int = 0
    exif_available: bool = False


class VideoScanner:

    def scan_folder(self, folder_path: str | Path) -> list[VideoClip]:
        folder = Path(folder_path)
        clips: list[VideoClip] = []

        paths = [
            p for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        ]
        paths = natsorted(paths, key=lambda p: str(p))

        THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

        for idx, video_path in enumerate(paths):
            try:
                clip = self._build_clip(video_path, idx)
                clips.append(clip)
            except Exception:
                pass

        return clips

    def sort_by_date(self, video_list: list[VideoClip]) -> list[VideoClip]:
        sorted_clips = sorted(video_list, key=lambda c: c.creation_date)
        for idx, clip in enumerate(sorted_clips):
            clip.order_index = idx
        return sorted_clips

    def get_thumbnail(self, video_path: str | Path, time_sec: float = 1.0) -> Optional[QPixmap]:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            frame_number = int(fps * time_sec)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            if not ret:
                return None
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            img = QImage(frame_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(img)
        finally:
            cap.release()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_clip(self, video_path: Path, idx: int) -> VideoClip:
        creation_date, exif_ok = self._get_creation_date(video_path)
        duration = self._get_duration(video_path)
        file_size = video_path.stat().st_size
        thumbnail_path = self._save_thumbnail(video_path)

        return VideoClip(
            path=video_path,
            name=video_path.name,
            duration=duration,
            creation_date=creation_date,
            file_size=file_size,
            thumbnail_path=thumbnail_path,
            order_index=idx,
            exif_available=exif_ok,
        )

    def _get_creation_date(self, video_path: Path) -> tuple[datetime, bool]:
        # Try EXIF first (suppress exifread noise on non-image files)
        import contextlib, io
        try:
            with video_path.open("rb") as f:
                with contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(io.StringIO()):
                    tags = exifread.process_file(f, stop_tag="EXIF DateTimeOriginal", details=False)
            for key in ("EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"):
                if key in tags:
                    return datetime.strptime(str(tags[key]), "%Y:%m:%d %H:%M:%S"), True
        except Exception:
            pass

        # Fallback: file modification time
        return datetime.fromtimestamp(video_path.stat().st_mtime), False

    def _get_duration(self, video_path: Path) -> float:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return 0.0
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            return frame_count / fps if fps else 0.0
        finally:
            cap.release()

    def _save_thumbnail(self, video_path: Path, time_sec: float = 1.0) -> Optional[Path]:
        thumb_path = THUMBNAIL_DIR / (video_path.stem + "_thumb.jpg")
        if thumb_path.exists():
            return thumb_path

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * time_sec))
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
            if not ret:
                return None
            cv2.imwrite(str(thumb_path), frame)
            return thumb_path
        finally:
            cap.release()
