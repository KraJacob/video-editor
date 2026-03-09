from __future__ import annotations

import json
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QMimeData, QByteArray
from PyQt6.QtGui import QPixmap, QIcon, QDrag
from PyQt6.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem, QAbstractItemView, QVBoxLayout,
)

from core.video_scanner import VideoClip

MIME_INTERNAL = "application/x-timeline-indices"
MIME_LIBRARY  = "application/x-videoclip-index"

THUMB_SIZE = QSize(160, 90)
ITEM_SIZE  = QSize(172, 122)


def _format_duration(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def _make_icon(clip: VideoClip) -> QIcon:
    if clip.thumbnail_path and clip.thumbnail_path.exists():
        px = QPixmap(str(clip.thumbnail_path)).scaled(
            THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    else:
        px = QPixmap(THUMB_SIZE)
        px.fill(Qt.GlobalColor.darkGray)
    return QIcon(px)


def _make_item(clip: VideoClip, position: int) -> QListWidgetItem:
    label = clip.name if len(clip.name) <= 18 else clip.name[:15] + "..."
    item = QListWidgetItem(_make_icon(clip), f"{label}\n{_format_duration(clip.duration)}")
    item.setSizeHint(ITEM_SIZE)
    item.setData(Qt.ItemDataRole.UserRole, clip)
    item.setToolTip(clip.name)
    return item


# ---------------------------------------------------------------------------
# Internal list widget
# ---------------------------------------------------------------------------

class _TimelineList(QListWidget):
    """QListWidget specialised for timeline use."""

    internal_order_changed = pyqtSignal()
    library_drop_requested = pyqtSignal(int, int)   # clip_index, insert_at

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(False)
        self.setIconSize(THUMB_SIZE)
        self.setGridSize(ITEM_SIZE)
        self.setSpacing(4)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Snap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)

    # ------------------------------------------------------------------
    # Drag start: tag selected indices so we can detect internal moves
    # ------------------------------------------------------------------

    def startDrag(self, supported_actions: Qt.DropAction) -> None:
        items = self.selectedItems()
        if not items:
            return
        indices = sorted(self.row(it) for it in items)
        mime = QMimeData()
        mime.setData(MIME_INTERNAL, QByteArray(json.dumps(indices).encode()))
        # also provide a pixmap preview from the first item
        icon_px = items[0].icon().pixmap(THUMB_SIZE)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(icon_px)
        drag.exec(Qt.DropAction.MoveAction)

    # ------------------------------------------------------------------
    # Drop handling
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat(MIME_INTERNAL) or md.hasFormat(MIME_LIBRARY):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat(MIME_INTERNAL) or md.hasFormat(MIME_LIBRARY):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        drop_pos = event.position().toPoint()
        target_item = self.itemAt(drop_pos)
        insert_at = self.row(target_item) if target_item else self.count()

        if md.hasFormat(MIME_INTERNAL):
            indices: list[int] = json.loads(bytes(md.data(MIME_INTERNAL)).decode())
            self._move_items(indices, insert_at)
            event.acceptProposedAction()
            self.internal_order_changed.emit()

        elif md.hasFormat(MIME_LIBRARY):
            clip_index: int = json.loads(bytes(md.data(MIME_LIBRARY)).decode())
            event.acceptProposedAction()
            self.library_drop_requested.emit(clip_index, insert_at)

        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Internal reorder helper
    # ------------------------------------------------------------------

    def _move_items(self, indices: list[int], insert_at: int) -> None:
        """Remove items at *indices* and re-insert them at *insert_at*."""
        items_data: list[tuple[QIcon, str, VideoClip]] = []
        for idx in sorted(indices, reverse=True):
            it = self.takeItem(idx)
            items_data.insert(0, (it.icon(), it.text(), it.data(Qt.ItemDataRole.UserRole)))
            if idx < insert_at:
                insert_at -= 1

        for icon, text, clip in items_data:
            new_item = QListWidgetItem(icon, text)
            new_item.setSizeHint(ITEM_SIZE)
            new_item.setData(Qt.ItemDataRole.UserRole, clip)
            new_item.setToolTip(clip.name)
            self.insertItem(insert_at, new_item)
            insert_at += 1


# ---------------------------------------------------------------------------
# Public TimelineWidget
# ---------------------------------------------------------------------------

class TimelineWidget(QWidget):
    order_changed          = pyqtSignal(list)   # list[VideoClip]
    clip_selected          = pyqtSignal(object) # VideoClip
    clip_removed           = pyqtSignal(int)    # former index
    library_drop_requested = pyqtSignal(int, int)  # clip_row, insert_at

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._list = _TimelineList(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._list)

        self._list.internal_order_changed.connect(self._on_order_changed)
        self._list.library_drop_requested.connect(self._on_library_drop)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_clips(self, clips: list[VideoClip]) -> None:
        self._list.clear()
        for i, clip in enumerate(clips):
            self._list.addItem(_make_item(clip, i))

    def add_clip(self, clip: VideoClip, position: Optional[int] = None) -> None:
        if position is None:
            position = self._list.count()
        self._list.insertItem(position, _make_item(clip, position))
        self._emit_order_changed()

    def clips(self) -> list[VideoClip]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    def mark_duplicates(self) -> None:
        """Prefix ⚠ to items whose creation_date is shared with another clip."""
        from collections import Counter
        clips = self.clips()
        counts = Counter(c.creation_date for c in clips)
        for i in range(self._list.count()):
            item = self._list.item(i)
            clip = item.data(Qt.ItemDataRole.UserRole)
            label = clip.name if len(clip.name) <= 18 else clip.name[:15] + "..."
            text  = f"{label}\n{_format_duration(clip.duration)}"
            if counts[clip.creation_date] > 1:
                text = f"⚠ {text}"
                item.setToolTip(f"{clip.name}\n⚠ Date EXIF en double !")
            else:
                item.setToolTip(clip.name)
            item.setText(text)

    # ------------------------------------------------------------------
    # Key events
    # ------------------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._delete_selected()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_order_changed(self) -> None:
        self._emit_order_changed()

    def _on_library_drop(self, clip_row: int, insert_at: int) -> None:
        self.library_drop_requested.emit(clip_row, insert_at)

    def _on_selection_changed(self) -> None:
        selected = self._list.selectedItems()
        if len(selected) == 1:
            clip: VideoClip = selected[0].data(Qt.ItemDataRole.UserRole)
            self.clip_selected.emit(clip)

    def _delete_selected(self) -> None:
        rows = sorted(
            (self._list.row(it) for it in self._list.selectedItems()),
            reverse=True,
        )
        for row in rows:
            self._list.takeItem(row)
            self.clip_removed.emit(row)
        if rows:
            self._emit_order_changed()

    def _emit_order_changed(self) -> None:
        self.order_changed.emit(self.clips())

    # ------------------------------------------------------------------
    # Library drag support: returns the MIME type & builder for the library
    # ------------------------------------------------------------------

    @staticmethod
    def library_mime_type() -> str:
        return MIME_LIBRARY

    @staticmethod
    def make_library_mime(clip_index: int) -> QMimeData:
        mime = QMimeData()
        mime.setData(MIME_LIBRARY, QByteArray(json.dumps(clip_index).encode()))
        return mime
