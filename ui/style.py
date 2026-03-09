DARK_QSS = """
/* ── VideoAssembler dark theme (Catppuccin Mocha palette) ── */

QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #181825;
}

/* ── Menu bar ── */
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}
QMenuBar::item:selected { background-color: #313244; }
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #313244;
}
QMenu::item:selected { background-color: #45475a; }
QMenu::separator     { height: 1px; background: #313244; margin: 2px 8px; }

/* ── Toolbar ── */
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    spacing: 4px;
    padding: 2px 6px;
}
QToolButton {
    background-color: transparent;
    color: #cdd6f4;
    border: none;
    padding: 4px 10px;
    border-radius: 4px;
}
QToolButton:hover   { background-color: #313244; }
QToolButton:pressed { background-color: #45475a; }

/* ── Buttons ── */
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 14px;
    min-height: 24px;
}
QPushButton:hover    { background-color: #45475a; }
QPushButton:pressed  { background-color: #585b70; }
QPushButton:disabled { background-color: #252535; color: #6c7086; }

/* ── Inputs ── */
QLineEdit, QDoubleSpinBox, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 24px;
}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {
    border-color: #89b4fa;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #45475a;
    border: none;
    width: 16px;
}

/* ── ComboBox ── */
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 24px;
}
QComboBox:hover                { border-color: #585b70; }
QComboBox::drop-down           { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #45475a;
    border: 1px solid #45475a;
}

/* ── Lists ── */
QListWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    outline: 0;
}
QListWidget::item:selected { background-color: #45475a; }
QListWidget::item:hover    { background-color: #2a2a3e; }

/* ── Group box ── */
QGroupBox {
    color: #89b4fa;
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
}

/* ── Progress bar ── */
QProgressBar {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    min-height: 16px;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

/* ── Splitter ── */
QSplitter::handle             { background-color: #313244; }
QSplitter::handle:horizontal  { width: 2px; }
QSplitter::handle:vertical    { height: 2px; }

/* ── Scrollbars ── */
QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover    { background-color: #585b70; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical        { height: 0; }

QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    border: none;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover  { background-color: #585b70; }
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal      { width: 0; }

/* ── Status bar ── */
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
    border-top: 1px solid #313244;
}
QStatusBar QLabel { background: transparent; }

/* ── Tooltip ── */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    padding: 4px 8px;
    border-radius: 4px;
}

/* ── Label (transparent bg) ── */
QLabel { background-color: transparent; }

/* ── VLine separator ── */
QFrame[frameShape="5"] { color: #313244; }
"""
