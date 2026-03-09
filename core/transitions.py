from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional, Tuple, Union

import cv2
import numpy as np

from moviepy import CompositeVideoClip, TextClip, VideoClip, concatenate_videoclips
import moviepy.video.fx as vfx

# Position type accepted by add_text_overlay
Position = Union[str, Tuple[int, int]]

# Default font path (Linux fallback; override via FONT_PATH)
_DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path: Optional[str] = None) -> str:
    candidate = Path(path or _DEFAULT_FONT)
    if candidate.exists():
        return str(candidate)
    # Try common fallbacks
    for fb in [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if Path(fb).exists():
            return fb
    return str(candidate)   # best-effort; TextClip will raise a clear error


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TransitionEffect(ABC):
    name: str = ""
    description: str = ""
    default_duration: float = 0.5

    @abstractmethod
    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        """Return a single VideoClip that blends clip1 into clip2."""


# ---------------------------------------------------------------------------
# Concrete transitions
# ---------------------------------------------------------------------------

class NoTransition(TransitionEffect):
    name = "Aucune"
    description = "Coupe sèche directe entre les deux clips."

    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        return concatenate_videoclips([clip1, clip2])


class FadeTransition(TransitionEffect):
    name = "Fondu noir"
    description = "Fondu au noir en sortie de clip1, fondu depuis le noir en entrée de clip2."

    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        dur = min(duration, clip1.duration / 2, clip2.duration / 2)
        c1 = clip1.with_effects([vfx.FadeOut(dur)])
        c2 = clip2.with_effects([vfx.FadeIn(dur)])
        return concatenate_videoclips([c1, c2])


class CrossfadeTransition(TransitionEffect):
    name = "Fondu enchaîné"
    description = "Superposition progressive de clip1 et clip2 (crossfade)."

    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        dur = min(duration, clip1.duration / 2, clip2.duration / 2)
        return concatenate_videoclips(
            [
                clip1.with_effects([vfx.CrossFadeOut(dur)]),
                clip2.with_effects([vfx.CrossFadeIn(dur)]),
            ],
            method="compose",
            padding=-dur,
        )


class SlideLeftTransition(TransitionEffect):
    name = "Glissement gauche"
    description = "clip2 entre par la droite en poussant clip1 vers la gauche."

    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        dur = min(duration, clip1.duration / 2, clip2.duration / 2)
        W = clip1.w

        c1_end   = clip1.subclipped(clip1.duration - dur).with_position(
            lambda t: (-int(W * t / dur), 0)
        )
        c2_start = clip2.subclipped(0, dur).with_position(
            lambda t: (W - int(W * t / dur), 0)
        )
        transition = CompositeVideoClip([c1_end, c2_start], size=clip1.size)

        main1 = clip1.subclipped(0, clip1.duration - dur)
        main2 = clip2.subclipped(dur)
        return concatenate_videoclips([main1, transition, main2])


class SlideRightTransition(TransitionEffect):
    name = "Glissement droite"
    description = "clip2 entre par la gauche en poussant clip1 vers la droite."

    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        dur = min(duration, clip1.duration / 2, clip2.duration / 2)
        W = clip1.w

        c1_end   = clip1.subclipped(clip1.duration - dur).with_position(
            lambda t: (int(W * t / dur), 0)
        )
        c2_start = clip2.subclipped(0, dur).with_position(
            lambda t: (-W + int(W * t / dur), 0)
        )
        transition = CompositeVideoClip([c1_end, c2_start], size=clip1.size)

        main1 = clip1.subclipped(0, clip1.duration - dur)
        main2 = clip2.subclipped(dur)
        return concatenate_videoclips([main1, transition, main2])


class ZoomTransition(TransitionEffect):
    name = "Zoom"
    description = "Zoom progressif sur clip1 avant l'arrivée de clip2."

    def apply(self, clip1: VideoClip, clip2: VideoClip, duration: float = 0.5) -> VideoClip:
        dur = min(duration, clip1.duration / 2)

        def zoom_frame(get_frame, t: float):
            frame = get_frame(t)
            h, w  = frame.shape[:2]
            progress = min(t / dur, 1.0)
            scale    = 1.0 + 0.4 * progress
            new_w, new_h = int(w * scale), int(h * scale)
            zoomed = cv2.resize(frame, (new_w, new_h))
            x = (new_w - w) // 2
            y = (new_h - h) // 2
            return zoomed[y: y + h, x: x + w]

        c1_main = clip1.subclipped(0, clip1.duration - dur)
        c1_zoom = clip1.subclipped(clip1.duration - dur).transform(zoom_frame)
        return concatenate_videoclips([c1_main, c1_zoom, clip2])


# ---------------------------------------------------------------------------
# EffectProcessor — single-clip effects
# ---------------------------------------------------------------------------

class EffectProcessor:

    @staticmethod
    def brightness_contrast(
        clip: VideoClip,
        brightness: float = 0.0,
        contrast: float = 1.0,
    ) -> VideoClip:
        """Adjust brightness ([-1, 1]) and contrast ([0, ∞]) of every frame."""
        def adjust(frame: np.ndarray) -> np.ndarray:
            f = frame.astype(np.float32)
            f = f * contrast + brightness * 255.0
            return np.clip(f, 0, 255).astype(np.uint8)

        return clip.image_transform(adjust)

    @staticmethod
    def stabilize(clip: VideoClip) -> VideoClip:
        """Basic motion stabilisation via optical-flow trajectory smoothing."""
        frames = [clip.get_frame(t) for t in np.arange(0, clip.duration, 1.0 / clip.fps)]
        n = len(frames)
        if n < 2:
            return clip

        transforms: list[tuple[float, float, float]] = []
        prev_gray = cv2.cvtColor(frames[0], cv2.COLOR_RGB2GRAY)
        for i in range(1, n):
            curr_gray = cv2.cvtColor(frames[i], cv2.COLOR_RGB2GRAY)
            prev_pts  = cv2.goodFeaturesToTrack(prev_gray, 200, 0.01, 30)
            if prev_pts is None:
                transforms.append((0.0, 0.0, 0.0))
                prev_gray = curr_gray
                continue
            curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None)
            idx = np.where(status == 1)[0]
            M, _ = cv2.estimateAffinePartial2D(prev_pts[idx], curr_pts[idx])
            if M is None:
                transforms.append((0.0, 0.0, 0.0))
            else:
                transforms.append((M[0, 2], M[1, 2], np.arctan2(M[1, 0], M[0, 0])))
            prev_gray = curr_gray

        arr    = np.array(transforms)
        window = 15
        kernel = np.ones(window) / window
        smooth = np.apply_along_axis(lambda col: np.convolve(col, kernel, mode="same"), 0, arr)

        h, w = frames[0].shape[:2]
        stabilised: list[np.ndarray] = [frames[0]]
        for i, (dx, dy, da) in enumerate(smooth):
            M = cv2.getRotationMatrix2D((w / 2, h / 2), np.degrees(da), 1.0)
            M[0, 2] += dx
            M[1, 2] += dy
            fixed = cv2.warpAffine(frames[i + 1], M, (w, h), borderMode=cv2.BORDER_REFLECT)
            stabilised.append(fixed)

        def make_frame(t: float) -> np.ndarray:
            idx = min(int(t * clip.fps), len(stabilised) - 1)
            return stabilised[idx]

        return VideoClip(make_frame, duration=clip.duration).with_fps(clip.fps)

    @staticmethod
    def speed_change(clip: VideoClip, factor: float = 1.0) -> VideoClip:
        """Multiply playback speed by *factor* (>1 accelerate, <1 slow down)."""
        return clip.with_speed_scaled(factor)

    @staticmethod
    def add_text_overlay(
        clip: VideoClip,
        text: str,
        position: Position = "bottom",
        font_size: int = 40,
        color: str = "white",
        font_path: Optional[str] = None,
    ) -> VideoClip:
        """Burn *text* onto the clip for its full duration."""
        txt = (
            TextClip(
                font=_font(font_path),
                text=text,
                font_size=font_size,
                color=color,
                size=(clip.w, None),
            )
            .with_duration(clip.duration)
            .with_position(position)
        )
        return CompositeVideoClip([clip, txt])


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------

TRANSITIONS_REGISTRY: dict[str, TransitionEffect] = {
    t.name: t
    for t in [
        NoTransition(),
        FadeTransition(),
        CrossfadeTransition(),
        SlideLeftTransition(),
        SlideRightTransition(),
        ZoomTransition(),
    ]
}

EFFECTS_REGISTRY: dict[str, Callable] = {
    "brightness_contrast": EffectProcessor.brightness_contrast,
    "stabilize":           EffectProcessor.stabilize,
    "speed_change":        EffectProcessor.speed_change,
    "add_text_overlay":    EffectProcessor.add_text_overlay,
}
