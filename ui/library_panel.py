from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QDrag
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QProgressBar, QComboBox, QLabel, QFileDialog,
    QAbstractItemView,
)

from core.video_scanner import VideoClip, VideoScanner, VIDEO_EXTENSIONS
from ui.timeline import TimelineWidget

THUMB_SIZE = QSize(96, 54)
ITEM_SIZE  = QSize(0, 64)          # width 0 → stretches to list width


def _fmt(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _truncate(name: str, n: int = 26) -> str:
    return name if len(name) <= n else name[: n - 3] + "..."


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class ScanWorker(QThread):
    progress = pyqtSignal(int, int)   # current, total
    finished = pyqtSignal(list)       # list[VideoClip]
    error    = pyqtSignal(str)

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self._folder  = folder
        self._scanner = VideoScanner()

    def run(self) -> None:
        try:
            from natsort import natsorted
            paths = natsorted(
                [p for p in self._folder.rglob("*")
                 if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS],
                key=str,
            )
            total = len(paths)
            clips: list[VideoClip] = []
            for i, path in enumerate(paths):
                self.progress.emit(i + 1, total)
                try:
                    clips.append(self._scanner._build_clip(path, i))
                except Exception:
                    pass
            self.finished.emit(clips)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Draggable QListWidget
# ---------------------------------------------------------------------------

class _LibraryList(QListWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setIconSize(THUMB_SIZE)
        self.setSpacing(2)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        item = self.currentItem()
        if item is None:
            return
        row = self.row(item)
        mime = TimelineWidget.make_library_mime(row)
        px = item.icon().pixmap(THUMB_SIZE)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(px)
        drag.exec(Qt.DropAction.CopyAction)


# ---------------------------------------------------------------------------
# Public LibraryPanel
# ---------------------------------------------------------------------------

class LibraryPanel(QWidget):
    clips_loaded = pyqtSignal(list)   # list[VideoClip], emitted after scan

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._clips: list[VideoClip] = []
        self._worker: Optional[ScanWorker] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_clip_at(self, row: int) -> Optional[VideoClip]:
        """Return the clip currently displayed at *row* (after sorting)."""
        item = self._list.item(row)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Open folder button
        self._btn_open = QPushButton("Ouvrir dossier")
        self._btn_open.clicked.connect(self._open_folder)
        layout.addWidget(self._btn_open)

        # Sort controls
        sort_row = QHBoxLayout()
        sort_row.addWidget(QLabel("Trier :"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItems(["Date EXIF", "Nom", "Durée"])
        self._sort_combo.currentIndexChanged.connect(self._apply_sort)
        sort_row.addWidget(self._sort_combo, stretch=1)
        layout.addLayout(sort_row)

        # Progress bar (hidden by default)
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Clip list
        self._list = _LibraryList()
        layout.addWidget(self._list, stretch=1)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Ouvrir un dossier vidéo")
        if folder:
            self._start_scan(Path(folder))

    def _start_scan(self, folder: Path) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._clips.clear()
        self._list.clear()
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._btn_open.setEnabled(False)

        self._worker = ScanWorker(folder)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(current)
        self._progress.setFormat(f"{current} / {total}")

    def _on_finished(self, clips: list[VideoClip]) -> None:
        self._clips = clips
        self._progress.setVisible(False)
        self._btn_open.setEnabled(True)
        self._apply_sort()
        self.clips_loaded.emit(self._clips)

    def _on_error(self, message: str) -> None:
        self._progress.setVisible(False)
        self._btn_open.setEnabled(True)

    def _apply_sort(self) -> None:
        idx = self._sort_combo.currentIndex()
        if idx == 0:
            ordered = VideoScanner().sort_by_date(list(self._clips))
        elif idx == 1:
            ordered = sorted(self._clips, key=lambda c: c.name.lower())
        else:
            ordered = sorted(self._clips, key=lambda c: c.duration)
        self._populate(ordered)

    # ------------------------------------------------------------------
    # List population
    # ------------------------------------------------------------------

    def _populate(self, clips: list[VideoClip]) -> None:
        self._list.clear()
        for clip in clips:
            self._list.addItem(self._make_item(clip))

    def _make_item(self, clip: VideoClip) -> QListWidgetItem:
        if clip.thumbnail_path and clip.thumbnail_path.exists():
            px = QPixmap(str(clip.thumbnail_path)).scaled(
                THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            px = QPixmap(THUMB_SIZE)
            px.fill(Qt.GlobalColor.darkGray)

        badge = "EXIF OK" if clip.exif_available else "Date fichier"
        text  = f"{_truncate(clip.name)}\n{_fmt(clip.duration)}  [{badge}]"

        item = QListWidgetItem(QIcon(px), text)
        item.setSizeHint(ITEM_SIZE)
        item.setData(Qt.ItemDataRole.UserRole, clip)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        item.setToolTip(f"{clip.name}\n{_fmt(clip.duration)}\n{badge}")
        return item
