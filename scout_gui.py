#!/usr/bin/env python3
"""
UCI Scout  ·  PyQt6 Desktop GUI
=========================================================
Launch with:
    python scout_gui.py
"""

from __future__ import annotations

import sys
import os
import json
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QSplitter, QFrame,
    QProgressBar, QStatusBar, QHeaderView, QComboBox, QCheckBox,
    QGroupBox, QScrollArea, QSizePolicy, QToolButton, QSpacerItem,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QSettings,
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QPixmap, QAction,
    QSyntaxHighlighter, QTextCharFormat,
)

# ── Allow running from any cwd ────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from scout import ScoutCrawler, CrawlResult, EntryPoint
from scout_manifest import generate_scaffold


# ─────────────────────────────────────────────────────────────────
# Palette / style constants
# ─────────────────────────────────────────────────────────────────

DARK_BG       = "#0D1117"
SURFACE       = "#161B22"
SURFACE2      = "#1C2230"
BORDER        = "#30363D"
ACCENT        = "#00B4D8"       # cyan — UCI Scout brand
ACCENT_DIM    = "#0A3040"
GREEN         = "#3FB950"
YELLOW        = "#E3B341"
RED           = "#F85149"
TEXT_PRI      = "#E6EDF3"
TEXT_SEC      = "#8B949E"
TEXT_DIM      = "#484F58"
MONO_FONT     = "JetBrains Mono, Consolas, Courier New, monospace"

RISK_COLOUR = {"low": GREEN, "medium": YELLOW, "high": RED, "none": TEXT_DIM, "critical": RED}

KIND_COLOUR = {
    "http_route":      ACCENT,
    "cli_command":     GREEN,
    "websocket":       YELLOW,
    "scheduler_task":  YELLOW,
    "event_hook":      "#C792EA",
    "rpc_handler":     "#82AAFF",
    "public_function": TEXT_SEC,
    "class_method":    TEXT_SEC,
}

KIND_LABEL = {
    "http_route":      "HTTP",
    "cli_command":     "CLI",
    "websocket":       "WS",
    "scheduler_task":  "SCHED",
    "event_hook":      "EVENT",
    "rpc_handler":     "RPC",
    "public_function": "FUNC",
    "class_method":    "METHOD",
}

APP_STYLESHEET = f"""
QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRI};
    font-family: "Segoe UI", "SF Pro Display", system-ui, sans-serif;
    font-size: 13px;
}}
QMainWindow {{
    background-color: {DARK_BG};
}}

/* ── Panels ── */
QFrame#surface {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QFrame#surface2 {{
    background-color: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

/* ── Line inputs ── */
QLineEdit {{
    background-color: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 10px;
    color: {TEXT_PRI};
    font-size: 13px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QLineEdit::placeholder {{
    color: {TEXT_DIM};
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 7px 16px;
    color: {TEXT_PRI};
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {SURFACE};
    border-color: {TEXT_DIM};
}}
QPushButton:pressed {{
    background-color: {DARK_BG};
}}
QPushButton#primary {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: {DARK_BG};
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background-color: #00C8EE;
    border-color: #00C8EE;
}}
QPushButton#primary:pressed {{
    background-color: #008FAF;
}}
QPushButton#primary:disabled {{
    background-color: {SURFACE2};
    border-color: {BORDER};
    color: {TEXT_DIM};
}}
QPushButton#danger {{
    color: {RED};
    border-color: {RED};
}}
QPushButton#danger:hover {{
    background-color: #3D1A1A;
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background-color: {SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background-color: transparent;
    border: 1px solid transparent;
    border-bottom: none;
    padding: 7px 18px;
    color: {TEXT_SEC};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 12px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {SURFACE};
    border-color: {BORDER};
    border-bottom-color: {SURFACE};
    color: {TEXT_PRI};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT_PRI};
}}

/* ── Tree / List ── */
QTreeWidget {{
    background-color: {SURFACE};
    border: none;
    border-radius: 6px;
    alternate-background-color: {SURFACE2};
    outline: none;
    font-size: 12px;
    font-family: {MONO_FONT};
}}
QTreeWidget::item {{
    padding: 5px 4px;
    border: none;
}}
QTreeWidget::item:selected {{
    background-color: {ACCENT_DIM};
    color: {TEXT_PRI};
    border-left: 2px solid {ACCENT};
}}
QTreeWidget::item:hover:!selected {{
    background-color: {SURFACE2};
}}
QHeaderView::section {{
    background-color: {SURFACE2};
    border: none;
    border-right: 1px solid {BORDER};
    padding: 6px 10px;
    color: {TEXT_SEC};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* ── TextEdit (JSON/log) ── */
QTextEdit {{
    background-color: {SURFACE};
    border: none;
    border-radius: 6px;
    color: {TEXT_PRI};
    font-family: {MONO_FONT};
    font-size: 12px;
    selection-background-color: {ACCENT_DIM};
    padding: 8px;
}}

/* ── Progress bar ── */
QProgressBar {{
    background-color: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {BORDER};
    width: 1px;
    height: 1px;
}}

/* ── ScrollBar ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_DIM};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {SURFACE};
    border-top: 1px solid {BORDER};
    color: {TEXT_SEC};
    font-size: 12px;
    padding: 0 8px;
}}

/* ── ComboBox ── */
QComboBox {{
    background-color: {SURFACE2};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRI};
    font-size: 12px;
    min-width: 80px;
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE2};
    border: 1px solid {BORDER};
    color: {TEXT_PRI};
    selection-background-color: {ACCENT_DIM};
}}

/* ── CheckBox ── */
QCheckBox {{
    color: {TEXT_SEC};
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background-color: {SURFACE2};
}}
QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

/* ── GroupBox ── */
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 20px;
    padding-top: 14px;
    padding-left: 10px;
    padding-right: 10px;
    padding-bottom: 8px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -1px;
    color: {TEXT_SEC};
    background-color: {DARK_BG};
    padding: 2px 8px;
}}

/* ── Label variants ── */
QLabel#heading {{
    font-size: 16px;
    font-weight: 600;
    color: {TEXT_PRI};
}}
QLabel#mono {{
    font-family: {MONO_FONT};
    font-size: 12px;
    color: {TEXT_SEC};
}}
QLabel#accent {{
    color: {ACCENT};
    font-weight: 600;
}}
"""


# ─────────────────────────────────────────────────────────────────
# Scan worker thread
# ─────────────────────────────────────────────────────────────────

class ScanWorker(QThread):
    progress = pyqtSignal(str)       # status messages
    finished = pyqtSignal(object)    # CrawlResult or None

    def __init__(self, path: str, depth: int):
        super().__init__()
        self.path = path
        self.depth = depth
        self._result: Optional[CrawlResult] = None

    def run(self):
        class _LogScout(ScoutCrawler):
            def __init__(self2, *a, **kw):
                super().__init__(*a, **kw)
            def _log(self2, msg: str):
                self.progress.emit(msg)

        try:
            crawler = _LogScout(self.path, max_depth=self.depth, quiet=False)
            result = crawler.crawl()
            self.finished.emit(result)
        except Exception as e:
            self.progress.emit(f"Error: {e}")
            self.finished.emit(None)


# ─────────────────────────────────────────────────────────────────
# Score ring widget
# ─────────────────────────────────────────────────────────────────

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QBrush, QConicalGradient
from PyQt6.QtCore import QRect, QRectF
import math

class ScoreRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._score = 0
        self.setMinimumSize(110, 110)
        self.setMaximumSize(110, 110)

    def set_score(self, score: int):
        self._score = score
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 10
        pen_w = 8

        # Track
        p.setPen(QPen(QColor(BORDER), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Arc
        if self._score > 0:
            if self._score >= 70:
                col = QColor(GREEN)
            elif self._score >= 40:
                col = QColor(YELLOW)
            else:
                col = QColor(RED)
            p.setPen(QPen(col, pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            span = int(self._score / 100 * 360 * 16)
            p.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2), 90 * 16, -span)

        # Score text
        if self._score >= 70:
            text_col = QColor(GREEN)
        elif self._score >= 40:
            text_col = QColor(YELLOW)
        else:
            text_col = QColor(RED) if self._score > 0 else QColor(TEXT_DIM)

        p.setPen(text_col)
        f = QFont("Segoe UI", 18, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(QRect(0, 0, w, h - 14), Qt.AlignmentFlag.AlignCenter, str(self._score))

        p.setPen(QColor(TEXT_DIM))
        f2 = QFont("Segoe UI", 8)
        p.setFont(f2)
        p.drawText(QRect(0, 18, w, h), Qt.AlignmentFlag.AlignCenter, "/100")
        p.end()


# ─────────────────────────────────────────────────────────────────
# Stat card
# ─────────────────────────────────────────────────────────────────

class StatCard(QFrame):
    def __init__(self, label: str, value: str = "—", sub: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("surface2")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(f"font-size:10px;font-weight:600;letter-spacing:0.06em;color:{TEXT_DIM};")
        lay.addWidget(self._lbl)

        self._val = QLabel(value)
        self._val.setStyleSheet(f"font-size:22px;font-weight:600;color:{TEXT_PRI};font-family:{MONO_FONT};")
        lay.addWidget(self._val)

        self._sub = QLabel(sub)
        self._sub.setStyleSheet(f"font-size:11px;color:{TEXT_DIM};")
        lay.addWidget(self._sub)

    def set_value(self, v: str, colour: str = TEXT_PRI):
        self._val.setText(v)
        self._val.setStyleSheet(f"font-size:22px;font-weight:600;color:{colour};font-family:{MONO_FONT};")

    def set_sub(self, s: str):
        self._sub.setText(s)


# ─────────────────────────────────────────────────────────────────
# Badge label
# ─────────────────────────────────────────────────────────────────

def make_badge(text: str, fg: str, bg: str = "") -> QLabel:
    lbl = QLabel(text)
    bg_part = f"background-color:{bg};" if bg else ""
    lbl.setStyleSheet(
        f"color:{fg};{bg_part}border:1px solid {fg};"
        f"border-radius:3px;padding:1px 6px;"
        f"font-size:10px;font-weight:600;font-family:{MONO_FONT};"
    )
    lbl.setFixedHeight(18)
    return lbl


# ─────────────────────────────────────────────────────────────────
# JSON syntax highlighter
# ─────────────────────────────────────────────────────────────────

class JsonHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self._rules: list[tuple] = []

        def fmt(col, bold=False):
            f = QTextCharFormat()
            f.setForeground(QColor(col))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f

        import re
        self._rules = [
            (re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"\s*:'), fmt("#79B8FF")),   # keys
            (re.compile(r':\s*"[^"\\]*(?:\\.[^"\\]*)*"'), fmt("#9ECBFF")),   # string vals
            (re.compile(r'\b(true|false|null)\b'), fmt("#F97583")),           # literals
            (re.compile(r'\b-?\d+\.?\d*\b'), fmt("#B392F0")),                # numbers
            (re.compile(r'[{}\[\]]'), fmt(TEXT_SEC, bold=True)),              # braces
        ]

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ─────────────────────────────────────────────────────────────────
# Entry point detail panel
# ─────────────────────────────────────────────────────────────────

class EntryPointDetail(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("surface2")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        self._name = QLabel("Select an entry point")
        self._name.setStyleSheet(f"font-size:14px;font-weight:600;color:{TEXT_PRI};font-family:{MONO_FONT};")
        self._name.setWordWrap(True)
        lay.addWidget(self._name)

        self._badges = QHBoxLayout()
        self._badges.setSpacing(6)
        lay.addLayout(self._badges)

        self._desc = QLabel("")
        self._desc.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;")
        self._desc.setWordWrap(True)
        lay.addWidget(self._desc)

        grid_frame = QFrame()
        grid = QVBoxLayout(grid_frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        self._rows: list[tuple[QLabel, QLabel]] = []
        for label in ("File", "Line", "Module", "Category", "Execution", "Params", "Return"):
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;font-weight:600;min-width:72px;")
            val = QLabel("—")
            val.setStyleSheet(f"color:{TEXT_SEC};font-size:11px;font-family:{MONO_FONT};")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            grid.addLayout(row)
            self._rows.append((lbl, val))

        lay.addWidget(grid_frame)
        lay.addStretch()

    def _clear_badges(self):
        while self._badges.count():
            item = self._badges.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_ep(self, ep: EntryPoint):
        self._name.setText(ep.name)
        self._clear_badges()

        kind_col = KIND_COLOUR.get(ep.kind, TEXT_SEC)
        self._badges.addWidget(make_badge(KIND_LABEL.get(ep.kind, ep.kind), kind_col))

        risk_col = RISK_COLOUR.get(ep.risk_guess, TEXT_SEC)
        self._badges.addWidget(make_badge(ep.risk_guess, risk_col))

        if ep.uci_category:
            self._badges.addWidget(make_badge(ep.uci_category, ACCENT))

        if ep.is_async:
            self._badges.addWidget(make_badge("async", "#C792EA"))

        self._badges.addStretch()

        self._desc.setText(ep.description or "No docstring found.")

        vals = [
            ep.file,
            str(ep.line),
            ep.module,
            ep.uci_category or "—",
            ep.uci_execution_mode,
            ", ".join(ep.params) if ep.params else "—",
            ep.return_hint or "—",
        ]
        for (lbl, val), v in zip(self._rows, vals):
            val.setText(v or "—")

    def clear(self):
        self._name.setText("Select an entry point")
        self._desc.setText("")
        self._clear_badges()
        for _, val in self._rows:
            val.setText("—")


# ─────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────

class ScoutWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UCI Scout")
        self.resize(1180, 780)
        self.setMinimumSize(900, 600)
        self._result: Optional[CrawlResult] = None
        self._worker: Optional[ScanWorker] = None
        self._scan_timer = QTimer()
        self._scan_timer.timeout.connect(self._tick_progress)
        self._tick = 0

        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._restore_settings()

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)

        root.addLayout(self._build_header())
        root.addLayout(self._build_path_bar())
        root.addWidget(self._build_progress_bar())

        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._main_splitter.setHandleWidth(1)

        self._main_splitter.addWidget(self._build_left_panel())
        self._main_splitter.addWidget(self._build_right_panel())
        self._main_splitter.setSizes([300, 880])
        self._main_splitter.setStretchFactor(1, 1)

        root.addWidget(self._main_splitter, 1)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready — select a project path and scan")

    def _build_header(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(12)

        logo = QLabel("SCOUT")
        logo.setStyleSheet(
            f"font-family:'Courier New',monospace;"
            f"font-size:22px;"
            f"font-weight:900;"
            f"color:{ACCENT};"
            f"letter-spacing:8px;"
            f"padding-right:4px;"
        )
        lay.addWidget(logo)

        title = QLabel("UCI Scout")
        title.setStyleSheet(f"font-size:18px;font-weight:600;color:{TEXT_PRI};letter-spacing:-0.3px;")
        lay.addWidget(title)

        ver = QLabel("v0.1.0")
        ver.setStyleSheet(f"font-size:11px;color:{TEXT_DIM};font-family:{MONO_FONT};margin-top:4px;")
        lay.addWidget(ver)

        lay.addStretch()

        self._uci_badge = QLabel("UCI not detected")
        self._uci_badge.setStyleSheet(
            f"color:{TEXT_DIM};border:1px solid {BORDER};"
            f"border-radius:10px;padding:3px 12px;font-size:11px;"
        )
        lay.addWidget(self._uci_badge)
        return lay

    def _build_path_bar(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(8)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to target Python project…")
        self._path_edit.returnPressed.connect(self._start_scan)
        lay.addWidget(self._path_edit, 1)

        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse)
        lay.addWidget(browse_btn)

        # Options
        depth_lbl = QLabel("Depth:")
        depth_lbl.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;")
        lay.addWidget(depth_lbl)

        self._depth_combo = QComboBox()
        for d in range(1, 13):
            self._depth_combo.addItem(str(d), d)
        self._depth_combo.setCurrentIndex(7)  # default 8
        self._depth_combo.setFixedWidth(60)
        lay.addWidget(self._depth_combo)

        self._scaffold_chk = QCheckBox("Generate scaffold")
        self._scaffold_chk.setChecked(True)
        lay.addWidget(self._scaffold_chk)

        self._scan_btn = QPushButton("  Scan  ")
        self._scan_btn.setObjectName("primary")
        self._scan_btn.setFixedWidth(80)
        self._scan_btn.clicked.connect(self._start_scan)
        lay.addWidget(self._scan_btn)

        return lay

    def _build_progress_bar(self) -> QProgressBar:
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setTextVisible(False)
        return self._progress

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Score + summary cards
        score_row = QHBoxLayout()
        score_row.setSpacing(10)

        self._score_ring = ScoreRing()
        score_row.addWidget(self._score_ring)

        cards_col = QVBoxLayout()
        cards_col.setSpacing(6)
        self._card_eps  = StatCard("Entry Points", "—")
        self._card_files = StatCard("Python Files", "—")
        cards_col.addWidget(self._card_eps)
        cards_col.addWidget(self._card_files)
        score_row.addLayout(cards_col, 1)

        lay.addLayout(score_row)

        # Frameworks
        fw_group = QGroupBox("Frameworks")
        fw_lay = QVBoxLayout(fw_group)
        fw_lay.setContentsMargins(8, 8, 8, 8)
        self._fw_label = QLabel("—")
        self._fw_label.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;font-family:{MONO_FONT};")
        self._fw_label.setWordWrap(True)
        fw_lay.addWidget(self._fw_label)
        lay.addWidget(fw_group)

        # Compatibility notes
        notes_group = QGroupBox("UCI Compatibility")
        notes_lay = QVBoxLayout(notes_group)
        notes_lay.setContentsMargins(8, 8, 8, 8)
        self._notes_label = QLabel("Run a scan to see compatibility notes.")
        self._notes_label.setStyleSheet(f"color:{TEXT_SEC};font-size:12px;")
        self._notes_label.setWordWrap(True)
        notes_lay.addWidget(self._notes_label)
        lay.addWidget(notes_group)

        # Detail panel
        self._ep_detail = EntryPointDetail()
        lay.addWidget(self._ep_detail, 1)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        # ── Entry Points tab ──────────────────────────────────────
        ep_widget = QWidget()
        ep_lay = QVBoxLayout(ep_widget)
        ep_lay.setContentsMargins(10, 10, 10, 10)
        ep_lay.setSpacing(8)

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter entry points…")
        self._filter_edit.textChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._filter_edit, 1)

        self._kind_combo = QComboBox()
        self._kind_combo.addItems(["All types", "HTTP routes", "CLI commands",
                                   "WebSockets", "Scheduled", "Events",
                                   "Functions", "Methods"])
        self._kind_combo.currentIndexChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._kind_combo)

        self._risk_combo = QComboBox()
        self._risk_combo.addItems(["All risks", "low", "medium", "high"])
        self._risk_combo.currentIndexChanged.connect(self._apply_filter)
        filter_bar.addWidget(self._risk_combo)

        ep_lay.addLayout(filter_bar)

        self._ep_tree = QTreeWidget()
        self._ep_tree.setHeaderLabels(["Type", "Name", "Risk", "Category", "File"])
        self._ep_tree.setAlternatingRowColors(True)
        self._ep_tree.setRootIsDecorated(False)
        self._ep_tree.setSortingEnabled(True)
        self._ep_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._ep_tree.header().setStretchLastSection(False)
        self._ep_tree.header().resizeSection(0, 72)
        self._ep_tree.header().resizeSection(2, 64)
        self._ep_tree.header().resizeSection(3, 100)
        self._ep_tree.header().resizeSection(4, 200)
        self._ep_tree.currentItemChanged.connect(self._on_ep_selected)
        ep_lay.addWidget(self._ep_tree, 1)

        self._ep_count = QLabel("")
        self._ep_count.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;font-family:{MONO_FONT};")
        ep_lay.addWidget(self._ep_count)

        self._tabs.addTab(ep_widget, "Entry Points")

        # ── Scaffold tab ──────────────────────────────────────────
        scaffold_widget = QWidget()
        sc_lay = QVBoxLayout(scaffold_widget)
        sc_lay.setContentsMargins(10, 10, 10, 10)
        sc_lay.setSpacing(8)

        sc_btns = QHBoxLayout()
        sc_btns.setSpacing(8)
        self._copy_scaffold_btn = QPushButton("Copy to clipboard")
        self._copy_scaffold_btn.clicked.connect(self._copy_scaffold)
        self._copy_scaffold_btn.setEnabled(False)
        sc_btns.addWidget(self._copy_scaffold_btn)

        self._save_scaffold_btn = QPushButton("Save as JSON…")
        self._save_scaffold_btn.clicked.connect(self._save_scaffold)
        self._save_scaffold_btn.setEnabled(False)
        sc_btns.addWidget(self._save_scaffold_btn)

        sc_btns.addStretch()
        self._scaffold_info = QLabel("Scaffold will appear here after a scan.")
        self._scaffold_info.setStyleSheet(f"color:{TEXT_DIM};font-size:11px;")
        sc_btns.addWidget(self._scaffold_info)
        sc_lay.addLayout(sc_btns)

        self._scaffold_edit = QTextEdit()
        self._scaffold_edit.setReadOnly(True)
        self._scaffold_edit.setPlaceholderText("UCI manifest scaffold will appear here…")
        self._scaffold_hl = JsonHighlighter(self._scaffold_edit.document())
        sc_lay.addWidget(self._scaffold_edit, 1)

        self._tabs.addTab(scaffold_widget, "UCI Scaffold")

        # ── JSON report tab ───────────────────────────────────────
        json_widget = QWidget()
        js_lay = QVBoxLayout(json_widget)
        js_lay.setContentsMargins(10, 10, 10, 10)
        js_lay.setSpacing(8)

        js_btns = QHBoxLayout()
        self._copy_json_btn = QPushButton("Copy to clipboard")
        self._copy_json_btn.clicked.connect(self._copy_json)
        self._copy_json_btn.setEnabled(False)
        js_btns.addWidget(self._copy_json_btn)
        self._save_json_btn = QPushButton("Save as JSON…")
        self._save_json_btn.clicked.connect(self._save_json)
        self._save_json_btn.setEnabled(False)
        js_btns.addWidget(self._save_json_btn)
        js_btns.addStretch()
        js_lay.addLayout(js_btns)

        self._json_edit = QTextEdit()
        self._json_edit.setReadOnly(True)
        self._json_edit.setPlaceholderText("Full JSON report will appear here…")
        self._json_hl = JsonHighlighter(self._json_edit.document())
        js_lay.addWidget(self._json_edit, 1)

        self._tabs.addTab(json_widget, "JSON Report")

        # ── Log tab ───────────────────────────────────────────────
        log_widget = QWidget()
        log_lay = QVBoxLayout(log_widget)
        log_lay.setContentsMargins(10, 10, 10, 10)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setPlaceholderText("Scan log will appear here…")
        log_lay.addWidget(self._log_edit)

        self._tabs.addTab(log_widget, "Scan Log")

        lay.addWidget(self._tabs, 1)
        return panel

    # ── Scan logic ────────────────────────────────────────────────

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select project directory")
        if path:
            self._path_edit.setText(path)

    def _start_scan(self):
        path = self._path_edit.text().strip()
        if not path:
            self._status.showMessage("Enter a project path first.")
            return
        if not Path(path).exists():
            self._status.showMessage(f"Path not found: {path}")
            return

        depth = self._depth_combo.currentData()
        self._set_scanning(True)
        self._log_edit.clear()
        self._log_append(f"Scanning: {path}")
        self._log_append(f"Max depth: {depth}")
        self._log_append("—" * 50)

        self._worker = ScanWorker(path, depth)
        self._worker.progress.connect(self._log_append)
        self._worker.finished.connect(self._on_scan_finished)
        self._worker.start()

        self._scan_timer.start(200)

    def _tick_progress(self):
        dots = "." * (self._tick % 4)
        self._status.showMessage(f"Scanning{dots}")
        self._tick += 1

    def _on_scan_finished(self, result: Optional[CrawlResult]):
        self._scan_timer.stop()
        self._set_scanning(False)
        self._log_append("—" * 50)

        if result is None:
            self._status.showMessage("Scan failed — check the log for details.")
            return

        self._result = result
        self._log_append(
            f"Done. {result.total_entry_points} entry points "
            f"across {result.python_files} Python files."
        )
        self._render_result(result)
        self._status.showMessage(
            f"Scan complete — {result.total_entry_points} entry points · "
            f"UCI score: {result.uci_compatibility_score}/100"
        )

    def _set_scanning(self, scanning: bool):
        self._scan_btn.setEnabled(not scanning)
        self._progress.setVisible(scanning)
        if scanning:
            self._scan_btn.setText("…")
        else:
            self._scan_btn.setText("Scan")
        self._tick = 0

    # ── Result rendering ──────────────────────────────────────────

    def _render_result(self, r: CrawlResult):
        score = r.uci_compatibility_score
        self._score_ring.set_score(score)

        ep_col = GREEN if r.total_entry_points > 0 else TEXT_DIM
        self._card_eps.set_value(str(r.total_entry_points), ep_col)
        self._card_eps.set_sub(f"{len(r.http_routes)} HTTP · {len(r.cli_commands)} CLI")
        self._card_files.set_value(str(r.python_files))
        self._card_files.set_sub(f"of {r.files_scanned} files scanned")

        # Frameworks
        if r.frameworks:
            fw_parts = []
            for fw in r.frameworks:
                col = ACCENT if fw == "uci" else TEXT_SEC
                fw_parts.append(f"<span style='color:{col}'>{fw}</span>")
            self._fw_label.setText("  ".join(fw_parts))
        else:
            self._fw_label.setText("None detected")

        # UCI badge
        if r.has_existing_uci:
            self._uci_badge.setText("✓  UCI detected")
            self._uci_badge.setStyleSheet(
                f"color:{GREEN};border:1px solid {GREEN};"
                f"border-radius:10px;padding:3px 12px;font-size:11px;"
            )
        else:
            self._uci_badge.setText("UCI not integrated")
            self._uci_badge.setStyleSheet(
                f"color:{TEXT_DIM};border:1px solid {BORDER};"
                f"border-radius:10px;padding:3px 12px;font-size:11px;"
            )

        # Compatibility notes
        if r.uci_compatibility_notes:
            lines = []
            for n in r.uci_compatibility_notes:
                icon = "✓" if n.startswith("✓") else "✗"
                col  = GREEN if icon == "✓" else RED
                body = n[2:].strip()
                lines.append(f"<span style='color:{col}'>{icon}</span> <span style='color:{TEXT_SEC}'>{body}</span>")
            self._notes_label.setText("<br>".join(lines))
        else:
            self._notes_label.setText("—")

        # Entry point tree
        self._populate_ep_tree(r)

        # Scaffold
        if self._scaffold_chk.isChecked():
            scaffold = generate_scaffold(r)
            scaffold_str = json.dumps(scaffold, indent=2)
            self._scaffold_edit.setPlainText(scaffold_str)
            self._scaffold_info.setText(
                f"{len(r.capabilities_for_scaffold(scaffold))} capabilities · "
                f"{sum(len(c.get('actions',[])) for c in scaffold.get('capabilities',[]))} actions"
            )
        else:
            self._scaffold_edit.setPlainText("(scaffold generation disabled)")
            self._scaffold_info.setText("")

        self._copy_scaffold_btn.setEnabled(True)
        self._save_scaffold_btn.setEnabled(True)

        # JSON report
        json_str = json.dumps(r.to_dict(), indent=2)
        self._json_edit.setPlainText(json_str)
        self._copy_json_btn.setEnabled(True)
        self._save_json_btn.setEnabled(True)

        self._ep_detail.clear()

    def _populate_ep_tree(self, r: CrawlResult):
        self._ep_tree.clear()
        all_eps = r.all_entry_points
        self._all_ep_items: list[tuple[EntryPoint, QTreeWidgetItem]] = []

        for ep in all_eps:
            item = QTreeWidgetItem()
            kind_label = KIND_LABEL.get(ep.kind, ep.kind)
            kind_col   = KIND_COLOUR.get(ep.kind, TEXT_SEC)
            risk_col   = RISK_COLOUR.get(ep.risk_guess, TEXT_SEC)

            item.setText(0, kind_label)
            item.setText(1, ep.name)
            item.setText(2, ep.risk_guess)
            item.setText(3, ep.uci_category or "utility")
            item.setText(4, f"{ep.file}:{ep.line}")

            item.setForeground(0, QColor(kind_col))
            item.setForeground(2, QColor(risk_col))
            item.setForeground(3, QColor(ACCENT))
            item.setForeground(4, QColor(TEXT_DIM))

            item.setData(0, Qt.ItemDataRole.UserRole, ep)
            self._ep_tree.addTopLevelItem(item)
            self._all_ep_items.append((ep, item))

        self._apply_filter()

    def _apply_filter(self):
        text = self._filter_edit.text().lower()
        kind_idx = self._kind_combo.currentIndex()
        risk_txt = self._risk_combo.currentText()

        kind_map = {
            1: "http_route", 2: "cli_command", 3: "websocket",
            4: "scheduler_task", 5: "event_hook",
            6: "public_function", 7: "class_method",
        }
        kind_filter = kind_map.get(kind_idx, None)

        visible = 0
        for ep, item in self._all_ep_items:
            show = True
            if text and not (
                text in ep.name.lower() or
                text in ep.file.lower() or
                text in (ep.uci_category or "").lower()
            ):
                show = False
            if kind_filter and ep.kind != kind_filter:
                show = False
            if risk_txt != "All risks" and ep.risk_guess != risk_txt:
                show = False
            item.setHidden(not show)
            if show:
                visible += 1

        total = len(self._all_ep_items)
        self._ep_count.setText(
            f"Showing {visible} of {total} entry points"
        )

    def _on_ep_selected(self, current: Optional[QTreeWidgetItem], _):
        if current is None:
            self._ep_detail.clear()
            return
        ep = current.data(0, Qt.ItemDataRole.UserRole)
        if ep:
            self._ep_detail.show_ep(ep)

    # ── Actions ───────────────────────────────────────────────────

    def _copy_scaffold(self):
        QApplication.clipboard().setText(self._scaffold_edit.toPlainText())
        self._status.showMessage("Scaffold copied to clipboard.")

    def _save_scaffold(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save UCI Manifest Scaffold",
            "uci_manifest_scaffold.json",
            "JSON files (*.json)"
        )
        if path:
            Path(path).write_text(self._scaffold_edit.toPlainText(), encoding="utf-8")
            self._status.showMessage(f"Scaffold saved: {path}")

    def _copy_json(self):
        QApplication.clipboard().setText(self._json_edit.toPlainText())
        self._status.showMessage("JSON report copied to clipboard.")

    def _save_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save JSON Report",
            "scout_report.json",
            "JSON files (*.json)"
        )
        if path:
            Path(path).write_text(self._json_edit.toPlainText(), encoding="utf-8")
            self._status.showMessage(f"Report saved: {path}")

    # ── Log helper ────────────────────────────────────────────────

    def _log_append(self, msg: str):
        self._log_edit.append(msg)
        self._log_edit.verticalScrollBar().setValue(
            self._log_edit.verticalScrollBar().maximum()
        )

    # ── Settings persistence ──────────────────────────────────────

    def _restore_settings(self):
        s = QSettings("LeonPriest", "UCI Scout")
        geom = s.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        last_path = s.value("last_path", "")
        if last_path:
            self._path_edit.setText(str(last_path))
        depth = s.value("depth", 8, type=int)
        idx = self._depth_combo.findData(depth)
        if idx >= 0:
            self._depth_combo.setCurrentIndex(idx)

    def closeEvent(self, event):
        s = QSettings("LeonPriest", "UCI Scout")
        s.setValue("geometry", self.saveGeometry())
        s.setValue("last_path", self._path_edit.text())
        s.setValue("depth", self._depth_combo.currentData())
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────
# Monkey-patch CrawlResult with a helper the GUI needs
# ─────────────────────────────────────────────────────────────────

def _capabilities_for_scaffold(self, scaffold: dict) -> list:
    return scaffold.get("capabilities", [])

CrawlResult.capabilities_for_scaffold = _capabilities_for_scaffold


# ─────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("UCI Scout")
    app.setOrganizationName("LeonPriest")
    app.setApplicationVersion("0.1.0")

    # High-DPI
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = ScoutWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
