from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from PyQt6.QtCore import QThread, pyqtSignal
from moviepy import VideoFileClip, concatenate_videoclips

from core.transitions import NoTransition, TransitionEffect
from core.video_scanner import VideoClip


# ---------------------------------------------------------------------------
# Export configuration
# ---------------------------------------------------------------------------

RESOLUTION_MAP: dict[str, Optional[tuple[int, int]]] = {
    "720p":     (1280, 720),
    "1080p":    (1920, 1080),
    "4K":       (3840, 2160),
    "original": None,
}

QUALITY_MAP: dict[str, dict] = {
    "draft":  {"crf": "28", "preset": "ultrafast"},
    "normal": {"crf": "23", "preset": "medium"},
    "high":   {"crf": "18", "preset": "slow"},
}

FPS_CHOICES = [24, 25, 30, 60]


@dataclass
class ExportOptions:
    resolution: str = "1080p"   # key of RESOLUTION_MAP
    fps: int = 30
    quality: str = "normal"     # key of QUALITY_MAP
    keep_audio: bool = True


# ---------------------------------------------------------------------------
# Main editor (stateless helpers)
# ---------------------------------------------------------------------------

class VideoEditor:
    """Assemble, preview and export video projects."""

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build_project(
        self,
        clips: list[VideoClip],
        transitions: Optional[list[TransitionEffect]] = None,
        *,
        options: Optional[ExportOptions] = None,
    ):
        """
        Load clips, apply transitions, and return a single MoviePy VideoClip.

        *transitions[i]* is applied between clips[i] and clips[i+1].
        Missing entries default to NoTransition.
        """
        if not clips:
            raise ValueError("No clips to assemble.")

        if transitions is None:
            transitions = []

        _no = NoTransition()

        moviepy_clips = [VideoFileClip(str(c.path)) for c in clips]

        # Apply transitions pairwise
        segments = []
        for i, mc in enumerate(moviepy_clips):
            if i == 0:
                segments.append(mc)
                continue
            trans = transitions[i - 1] if i - 1 < len(transitions) else _no
            prev = segments.pop()
            merged = trans.apply(prev, mc)
            segments.append(merged)

        final = concatenate_videoclips(segments, method="compose")

        if options and not options.keep_audio:
            final = final.without_audio()

        return final

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(
        self,
        moviepy_clip,
        output_path: str | Path,
        options: ExportOptions,
        *,
        progress_cb: Optional[Callable[[int], None]] = None,
        cancel_flag: Optional[list[bool]] = None,
        process_cb: Optional[Callable[[subprocess.Popen], None]] = None,
    ) -> None:
        """
        Export *moviepy_clip* to *output_path* via FFmpeg subprocess.

        Progress is reported as 0-100 via *progress_cb*.
        Pass a mutable list ``[False]`` as *cancel_flag*; set it to ``[True]``
        to request cancellation (the subprocess is then terminated).
        """
        output_path = Path(output_path)
        duration = moviepy_clip.duration
        quality = QUALITY_MAP[options.quality]
        res = RESOLUTION_MAP.get(options.resolution)

        # --- Phase 1 (0-50 %): write an intermediate file with MoviePy ----
        tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_path = Path(tmp_file.name)
        tmp_file.close()

        try:
            clip = moviepy_clip
            if res:
                clip = clip.resized(new_size=res)
            clip = clip.with_fps(options.fps)

            # Fast intermediate — correctness over quality
            clip.write_videofile(
                str(tmp_path),
                codec="libx264",
                preset="ultrafast",
                audio=options.keep_audio,
                audio_codec="aac" if options.keep_audio else None,
                ffmpeg_params=["-crf", "18"],
                logger=None,
            )

            if cancel_flag and cancel_flag[0]:
                return
            if progress_cb:
                progress_cb(50)

            # --- Phase 2 (50-100 %): FFmpeg re-encode with target quality --
            cmd = [
                "ffmpeg", "-y",
                "-i", str(tmp_path),
                "-vcodec", "libx264",
                "-crf", quality["crf"],
                "-preset", quality["preset"],
                "-movflags", "+faststart",
            ]
            if options.keep_audio:
                cmd += ["-acodec", "aac", "-b:a", "192k"]
            else:
                cmd += ["-an"]
            cmd.append(str(output_path))

            proc = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            if process_cb:
                process_cb(proc)

            for line in proc.stderr:
                if cancel_flag and cancel_flag[0]:
                    proc.terminate()
                    return
                m = re.search(r"time=(\d+):(\d+):(\d+\.\d+)", line)
                if m and progress_cb and duration:
                    elapsed = (
                        int(m.group(1)) * 3600
                        + int(m.group(2)) * 60
                        + float(m.group(3))
                    )
                    pct = 50 + int(50 * min(elapsed / duration, 1.0))
                    progress_cb(pct)

            proc.wait()
            if proc.returncode not in (0, None) and not (cancel_flag and cancel_flag[0]):
                raise RuntimeError(f"FFmpeg exited with code {proc.returncode}")

        finally:
            tmp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview_clip(
        self,
        clip: VideoClip,
        start: float = 0.0,
        end: Optional[float] = None,
        max_width: int = 640,
    ):
        """Return a low-resolution MoviePy clip for quick preview."""
        mv = VideoFileClip(str(clip.path))
        end = end if end is not None else mv.duration
        mv = mv.subclipped(start, min(end, mv.duration))
        if mv.w > max_width:
            mv = mv.resized(width=max_width)
        return mv


# ---------------------------------------------------------------------------
# QThread render worker
# ---------------------------------------------------------------------------

class RenderWorker(QThread):
    progress = pyqtSignal(int)   # 0-100
    finished = pyqtSignal(str)   # output path on success
    error    = pyqtSignal(str)   # error message

    def __init__(
        self,
        clips: list[VideoClip],
        transitions: list[TransitionEffect],
        output_path: str | Path,
        options: ExportOptions,
    ) -> None:
        super().__init__()
        self._clips       = clips
        self._transitions = transitions
        self._output_path = Path(output_path)
        self._options     = options
        self._editor      = VideoEditor()
        self._cancel_flag: list[bool] = [False]
        self._process: Optional[subprocess.Popen] = None

    def cancel(self) -> None:
        """Request cancellation. Terminates the FFmpeg subprocess if running."""
        self._cancel_flag[0] = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self) -> None:
        try:
            # Build MoviePy composite clip
            final = self._editor.build_project(
                self._clips,
                self._transitions,
                options=self._options,
            )

            if self._cancel_flag[0]:
                return

            # Export with progress reporting
            self._editor.export(
                final,
                self._output_path,
                self._options,
                progress_cb=self._on_progress,
                cancel_flag=self._cancel_flag,
                process_cb=self._register_process,
            )

            if not self._cancel_flag[0]:
                self.finished.emit(str(self._output_path))

        except Exception as exc:
            if not self._cancel_flag[0]:
                self.error.emit(str(exc))

    # ------------------------------------------------------------------
    # Internal callbacks (called from run() thread)
    # ------------------------------------------------------------------

    def _on_progress(self, pct: int) -> None:
        if not self._cancel_flag[0]:
            self.progress.emit(pct)

    def _register_process(self, proc: subprocess.Popen) -> None:
        self._process = proc
