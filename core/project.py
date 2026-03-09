from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.video_scanner import VideoClip, VideoScanner


class ProjectManager:
    """Save and restore .vap (VideoAssembler Project) files."""

    VERSION = 1
    SUFFIX  = ".vap"

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    @staticmethod
    def save(
        path: str | Path,
        clips: list[VideoClip],
        transition_name: str,
        transition_duration: float,
    ) -> None:
        data: dict[str, Any] = {
            "version": ProjectManager.VERSION,
            "transition": transition_name,
            "transition_duration": round(transition_duration, 2),
            "clips": [
                {"path": str(clip.path), "order": clip.order_index}
                for clip in clips
            ],
        }
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    @staticmethod
    def load(path: str | Path) -> dict[str, Any]:
        """
        Returns a dict with keys:
            clips               : list[VideoClip]
            transition          : str
            transition_duration : float
            missing             : list[str]   (paths that no longer exist)
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        scanner  = VideoScanner()
        clips:   list[VideoClip] = []
        missing: list[str]       = []

        for entry in raw.get("clips", []):
            clip_path = Path(entry["path"])
            if not clip_path.exists():
                missing.append(str(clip_path))
                continue
            try:
                clip = scanner._build_clip(clip_path, entry.get("order", 0))
                clips.append(clip)
            except Exception:
                missing.append(str(clip_path))

        return {
            "clips":               clips,
            "transition":          raw.get("transition", "Aucune"),
            "transition_duration": float(raw.get("transition_duration", 0.5)),
            "missing":             missing,
        }
