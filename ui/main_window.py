from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QSplitter, QToolBar, QVBoxLayout, QWidget, QFrame,
)

from core.project import ProjectManager
from core.transitions import TRANSITIONS_REGISTRY, NoTransition, TransitionEffect
from core.video_editor import (
    QUALITY_MAP, RESOLUTION_MAP, FPS_CHOICES, ExportOptions, RenderWorker,
)
from core.video_scanner import VideoClip
from ui.library_panel import LibraryPanel
from ui.timeline import TimelineWidget

# ---------------------------------------------------------------------------
# Video preview (thumbnail + open-in-VLC)
# ---------------------------------------------------------------------------

class VideoPreview(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._current_path: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._thumb = QLabel()
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet("background: #0d0d0d;")
        self._thumb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._thumb, stretch=1)

        self._btn = QPushButton("▶  Ouvrir dans VLC")
        self._btn.setVisible(False)
        self._btn.clicked.connect(self._open_in_vlc)
        layout.addWidget(self._btn)

    def play(self, path: str | Path) -> None:
        self._current_path = Path(path)
        self._show_thumbnail()
        self._btn.setVisible(True)

    def toggle(self) -> None:
        if self._current_path:
            self._open_in_vlc()

    def stop(self) -> None:
        pass  # no-op (external player)

    def _show_thumbnail(self) -> None:
        if not self._current_path:
            return
        # Try to load the saved thumbnail
        from core.video_scanner import THUMBNAIL_DIR
        thumb_path = THUMBNAIL_DIR / (self._current_path.stem + "_thumb.jpg")
        px: Optional[QPixmap] = None
        if thumb_path.exists():
            px = QPixmap(str(thumb_path))
        if px and not px.isNull():
            scaled = px.scaled(
                self._thumb.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb.setPixmap(scaled)
        else:
            self._thumb.setText("Pas de miniature disponible")
            self._thumb.setStyleSheet("background: #0d0d0d; color: #585b70;")

    def _open_in_vlc(self) -> None:
        if not self._current_path:
            return
        try:
            subprocess.Popen(["vlc", str(self._current_path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            QMessageBox.warning(None, "VLC introuvable",
                                "VLC n'est pas installé ou absent du PATH.")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._current_path:
            self._show_thumbnail()


# ---------------------------------------------------------------------------
# Properties panel
# ---------------------------------------------------------------------------

class PropertiesPanel(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        info_box = QGroupBox("Clip sélectionné")
        form = QFormLayout(info_box)
        self._lbl_name = QLabel("—")
        self._lbl_date = QLabel("—")
        self._lbl_dur  = QLabel("—")
        self._lbl_size = QLabel("—")
        self._lbl_exif = QLabel("—")
        for label, widget in [
            ("Nom :", self._lbl_name),
            ("Date :", self._lbl_date),
            ("Durée :", self._lbl_dur),
            ("Taille :", self._lbl_size),
            ("EXIF :", self._lbl_exif),
        ]:
            form.addRow(label, widget)
        layout.addWidget(info_box)
        layout.addStretch()

    def update_clip(self, clip: VideoClip) -> None:
        name = clip.name if len(clip.name) <= 22 else clip.name[:19] + "..."
        self._lbl_name.setText(name)
        self._lbl_date.setText(clip.creation_date.strftime("%Y-%m-%d %H:%M"))
        s = int(clip.duration)
        self._lbl_dur.setText(f"{s // 60}:{s % 60:02d}")
        self._lbl_size.setText(f"{clip.file_size / 1_048_576:.1f} Mo")
        self._lbl_exif.setText("EXIF OK" if clip.exif_available else "Date fichier")

    def clear(self) -> None:
        for w in (self._lbl_name, self._lbl_date, self._lbl_dur,
                  self._lbl_size, self._lbl_exif):
            w.setText("—")


# ---------------------------------------------------------------------------
# Export dialog
# ---------------------------------------------------------------------------

class ExportDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        clips: list[VideoClip],
        transition: TransitionEffect,
        transition_duration: float,
    ) -> None:
        super().__init__(parent)
        self._clips      = clips
        self._transition = transition
        self._trans_dur  = transition_duration
        self._worker: Optional[RenderWorker] = None
        self.setWindowTitle("Exporter le film")
        self.setMinimumWidth(460)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Chemin du fichier de sortie…")
        browse = QPushButton("…")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(browse)
        form.addRow("Fichier :", path_row)

        self._res_combo = QComboBox()
        self._res_combo.addItems(list(RESOLUTION_MAP.keys()))
        self._res_combo.setCurrentText("1080p")
        form.addRow("Résolution :", self._res_combo)

        self._fps_combo = QComboBox()
        self._fps_combo.addItems([str(f) for f in FPS_CHOICES])
        self._fps_combo.setCurrentText("30")
        form.addRow("FPS :", self._fps_combo)

        self._quality_combo = QComboBox()
        self._quality_combo.addItems(list(QUALITY_MAP.keys()))
        self._quality_combo.setCurrentText("normal")
        form.addRow("Qualité :", self._quality_combo)

        layout.addLayout(form)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setVisible(False)
        layout.addWidget(self._status_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._export_btn = QPushButton("Exporter")
        self._export_btn.clicked.connect(self._start_export)
        self._close_btn = QPushButton("Fermer")
        self._close_btn.clicked.connect(self._on_close)
        btn_row.addWidget(self._export_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer", "", "Vidéo MP4 (*.mp4)"
        )
        if path:
            self._path_edit.setText(path if path.endswith(".mp4") else path + ".mp4")

    def _start_export(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "Chemin manquant", "Choisissez un fichier de sortie.")
            return
        if not path.lower().endswith(".mp4"):
            path += ".mp4"
            self._path_edit.setText(path)
        options = ExportOptions(
            resolution=self._res_combo.currentText(),
            fps=int(self._fps_combo.currentText()),
            quality=self._quality_combo.currentText(),
        )
        n = len(self._clips)
        self._worker = RenderWorker(
            self._clips, [self._transition] * max(n - 1, 0), path, options
        )
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._export_btn.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status_lbl.setText("Export en cours…")
        self._status_lbl.setVisible(True)
        self._worker.start()

    def _on_close(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        self.reject()

    def _on_finished(self, path: str) -> None:
        self._progress.setValue(100)
        self._status_lbl.setText(f"Terminé : {path}")
        self._export_btn.setEnabled(True)
        QMessageBox.information(self, "Export terminé", f"Film exporté :\n{path}")

    def _on_error(self, msg: str) -> None:
        self._progress.setVisible(False)
        self._status_lbl.setVisible(False)
        self._export_btn.setEnabled(True)
        QMessageBox.critical(self, "Erreur d'export", msg)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__(parent=None)
        self._clips: list[VideoClip] = []
        self._current_clips: list[VideoClip] = []
        self._undo_stack: list[list[VideoClip]] = []
        self._undoing = False

        self.setWindowTitle("VideoAssembler - Montage automatique")
        self.setMinimumSize(1200, 700)
        self.setAcceptDrops(True)

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_status_bar()
        self._connect_signals()
        self._setup_shortcuts()
        self._update_status()

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("Fichier")

        act_open = QAction("Ouvrir dossier…", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_folder)
        file_menu.addAction(act_open)

        file_menu.addSeparator()

        act_save = QAction("Sauvegarder projet…", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._save_project)
        file_menu.addAction(act_save)

        act_load = QAction("Ouvrir projet…", self)
        act_load.setShortcut("Ctrl+P")
        act_load.triggered.connect(self._load_project)
        file_menu.addAction(act_load)

        file_menu.addSeparator()

        act_export = QAction("Exporter le film…", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._open_export_dialog)
        file_menu.addAction(act_export)

        file_menu.addSeparator()

        act_quit = QAction("Quitter", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        help_menu = mb.addMenu("Aide")
        act_about = QAction("À propos…", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principale", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addAction(self._make_action("Ouvrir dossier", self._open_folder))
        tb.addAction(self._make_action("Trier par date EXIF", self._sort_by_exif))
        tb.addSeparator()

        tb.addWidget(QLabel(" Transition : "))
        self._trans_combo = QComboBox()
        self._trans_combo.addItems(list(TRANSITIONS_REGISTRY.keys()))
        tb.addWidget(self._trans_combo)

        tb.addWidget(QLabel("  Durée : "))
        self._trans_spin = QDoubleSpinBox()
        self._trans_spin.setRange(0.1, 3.0)
        self._trans_spin.setSingleStep(0.1)
        self._trans_spin.setValue(0.5)
        self._trans_spin.setSuffix(" s")
        self._trans_spin.setFixedWidth(82)
        tb.addWidget(self._trans_spin)

        tb.addSeparator()
        tb.addAction(self._make_action("Aperçu", self._preview_first))
        tb.addAction(self._make_action("Exporter le film…", self._open_export_dialog))

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _build_central(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)

        h_split = QSplitter(Qt.Orientation.Horizontal)

        self._library = LibraryPanel()
        h_split.addWidget(self._library)

        v_split = QSplitter(Qt.Orientation.Vertical)
        self._preview  = VideoPreview()
        self._timeline = TimelineWidget()
        v_split.addWidget(self._preview)
        v_split.addWidget(self._timeline)
        v_split.setStretchFactor(0, 3)
        v_split.setStretchFactor(1, 1)
        h_split.addWidget(v_split)

        self._properties = PropertiesPanel()
        h_split.addWidget(self._properties)

        h_split.setStretchFactor(0, 3)
        h_split.setStretchFactor(1, 5)
        h_split.setStretchFactor(2, 2)

        outer.addWidget(h_split)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _build_status_bar(self) -> None:
        sb = self.statusBar()
        self._sb_clips    = QLabel("0 clip(s)")
        self._sb_duration = QLabel("Durée : 0:00")
        self._sb_disk     = QLabel("Espace estimé : 0.0 Mo")
        for w in (self._sb_clips, self._sb_duration, self._sb_disk):
            sb.addWidget(w)
            sb.addWidget(_vline())

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------

    def _setup_shortcuts(self) -> None:
        ctx = Qt.ShortcutContext.ApplicationShortcut

        space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space.setContext(ctx)
        space.activated.connect(self._preview.toggle)

        undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo.setContext(ctx)
        undo.activated.connect(self._undo)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._library.clips_loaded.connect(self._on_clips_loaded)
        self._timeline.order_changed.connect(self._on_order_changed)
        self._timeline.clip_selected.connect(self._on_clip_selected)
        self._timeline.clip_removed.connect(self._on_clip_removed)
        self._timeline.library_drop_requested.connect(self._on_library_drop)

    # ------------------------------------------------------------------
    # Drag & drop folder onto main window
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).is_dir():
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            folder = Path(urls[0].toLocalFile())
            if folder.is_dir():
                self._library._start_scan(folder)
                event.acceptProposedAction()
                return
        event.ignore()

    # ------------------------------------------------------------------
    # Project save / load
    # ------------------------------------------------------------------

    def _save_project(self) -> None:
        clips = self._timeline.clips()
        if not clips:
            QMessageBox.warning(self, "Projet vide", "La timeline est vide.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le projet", "",
            f"Projet VideoAssembler (*{ProjectManager.SUFFIX})"
        )
        if not path:
            return
        if not path.endswith(ProjectManager.SUFFIX):
            path += ProjectManager.SUFFIX
        try:
            ProjectManager.save(
                path, clips,
                self._trans_combo.currentText(),
                self._trans_spin.value(),
            )
            self.statusBar().showMessage(f"Projet sauvegardé : {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de sauvegarder :\n{exc}")

    def _load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un projet", "",
            f"Projet VideoAssembler (*{ProjectManager.SUFFIX})"
        )
        if not path:
            return
        try:
            result = ProjectManager.load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir :\n{exc}")
            return

        clips = result["clips"]
        if result["missing"]:
            missing_txt = "\n".join(result["missing"][:10])
            QMessageBox.warning(
                self, "Fichiers manquants",
                f"Ces fichiers sont introuvables et ont été ignorés :\n{missing_txt}"
            )

        self._undo_stack.clear()
        self._current_clips = list(clips)
        self._timeline.set_clips(clips)

        trans_name = result["transition"]
        if trans_name in TRANSITIONS_REGISTRY:
            self._trans_combo.setCurrentText(trans_name)
        self._trans_spin.setValue(result["transition_duration"])

        self._update_status()
        self._mark_duplicates()
        self.statusBar().showMessage(f"Projet chargé : {path}", 4000)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _open_folder(self) -> None:
        self._library._open_folder()

    def _sort_by_exif(self) -> None:
        self._library._sort_combo.setCurrentText("Date EXIF")
        self._library._apply_sort()

    def _on_clips_loaded(self, clips: list[VideoClip]) -> None:
        self._clips = clips
        self._undo_stack.clear()
        self._current_clips = list(clips)
        self._timeline.set_clips(clips)
        self._update_status()
        self._mark_duplicates()

    def _on_order_changed(self, clips: list[VideoClip]) -> None:
        if not self._undoing:
            self._undo_stack.append(list(self._current_clips))
        self._current_clips = list(clips)
        self._update_status()
        self._mark_duplicates()

    def _on_clip_selected(self, clip: VideoClip) -> None:
        self._properties.update_clip(clip)
        self._preview.play(clip.path)

    def _on_clip_removed(self, _row: int) -> None:
        self._update_status()
        self._mark_duplicates()

    def _on_library_drop(self, clip_row: int, insert_at: int) -> None:
        clip = self._library.get_clip_at(clip_row)
        if clip is not None:
            self._timeline.add_clip(clip, insert_at)

    def _preview_first(self) -> None:
        clips = self._timeline.clips()
        if not clips:
            QMessageBox.information(self, "Aperçu", "La timeline est vide.")
            return
        self._preview.play(clips[0].path)

    def _open_export_dialog(self) -> None:
        clips = self._timeline.clips()
        if not clips:
            QMessageBox.warning(self, "Export", "La timeline est vide.")
            return
        transition = TRANSITIONS_REGISTRY.get(
            self._trans_combo.currentText(), NoTransition()
        )
        ExportDialog(self, clips, transition, self._trans_spin.value()).exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "À propos de VideoAssembler",
            "<b>VideoAssembler</b> — Montage automatique<br><br>"
            "Éditeur vidéo desktop Python / PyQt6.<br>"
            "Tri EXIF · Transitions MoviePy · Export FFmpeg",
        )

    def _undo(self) -> None:
        if not self._undo_stack:
            self.statusBar().showMessage("Rien à annuler.", 2000)
            return
        self._undoing = True
        prev = self._undo_stack.pop()
        self._current_clips = list(prev)
        self._timeline.set_clips(prev)
        self._update_status()
        self._mark_duplicates()
        self._undoing = False
        self.statusBar().showMessage("Annulation effectuée.", 2000)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mark_duplicates(self) -> None:
        self._timeline.mark_duplicates()

    def _update_status(self) -> None:
        clips = self._timeline.clips()
        total = sum(c.duration for c in clips)
        m, s  = divmod(int(total), 60)
        est   = total / 60.0 * 10.0
        self._sb_clips.setText(f"{len(clips)} clip(s)")
        self._sb_duration.setText(f"Durée : {m}:{s:02d}")
        self._sb_disk.setText(f"Espace estimé : {est:.1f} Mo")

    @staticmethod
    def _make_action(label: str, slot) -> QAction:
        act = QAction(label)
        act.triggered.connect(slot)
        return act


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f
