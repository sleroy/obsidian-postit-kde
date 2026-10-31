"""Visual theme: a dark, violet-accented stylesheet and shared UI blocks.

Designed to sit naturally on a dark Plasma desktop rather than forcing a light
card onto it. All colors are explicit so the look is stable regardless of the
active Plasma color scheme.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

# Brand palette (matches resources/icon.svg)
ACCENT = "#8b5cf6"  # violet-500
ACCENT_HOVER = "#a78bfa"  # violet-400
ACCENT_DARK = "#6d28d9"  # violet-700

# Dark surfaces
BG = "#1b1b24"  # window background
CARD = "#24242f"  # card surface
FIELD = "#2d2d3a"  # input background
BORDER = "#3a3a4a"
TEXT = "#e7e5ee"  # primary text
MUTED = "#9a97a8"  # secondary text
ACCENT_TINT = "#2a2340"  # subtle violet-tinted surface

STYLESHEET = f"""
QDialog {{
    background: {BG};
}}

/* Header band */
#HeaderBand {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {ACCENT}, stop:1 {ACCENT_DARK});
    border: none;
}}
#HeaderTitle {{ color: #ffffff; font-size: 16px; font-weight: 700; }}
#HeaderSubtitle {{ color: #e9e3ff; font-size: 11px; }}

/* Card container */
#Card {{
    background: {CARD};
    border: none;
}}

QLabel {{ color: {TEXT}; }}
QLabel#FieldLabel {{
    color: {MUTED};
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 1px;
}}
QLabel#Hint {{ color: {MUTED}; font-size: 11px; }}
QLabel#TargetPreview {{
    color: {ACCENT_HOVER};
    font-size: 11px;
    font-weight: 600;
    padding: 2px 0 2px 2px;
}}

/* Inputs */
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {FIELD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 6px 9px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit::placeholder, QPlainTextEdit::placeholder {{ color: {MUTED}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {FIELD};
    color: {TEXT};
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    border: 1px solid {BORDER};
    outline: none;
}}

/* Buttons */
QPushButton {{
    background: {FIELD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 7px;
    padding: 7px 14px;
    font-weight: 600;
}}
QPushButton:hover {{ border: 1px solid {ACCENT}; color: {ACCENT_HOVER}; }}
QPushButton:disabled {{ color: #5f5c6e; background: #26262f; border: 1px solid #30303c; }}

QPushButton#Primary {{
    background: {ACCENT};
    color: #ffffff;
    border: 1px solid {ACCENT_DARK};
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; color: #1b1b24; }}
QPushButton#Primary:disabled {{ background: #4b3d79; border: 1px solid #4b3d79; color: #c9c2e6; }}

QPushButton#Assist {{
    background: {ACCENT_TINT};
    color: {ACCENT_HOVER};
    border: 1px solid #3d3560;
}}
QPushButton#Assist:hover {{ background: #332a52; border: 1px solid {ACCENT}; }}

QCheckBox {{ color: {TEXT}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {FIELD};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border: 1px solid {ACCENT_DARK};
}}

/* Paper surfaces — the diary document and its editors are intentionally a
   light "paper" on the dark chrome, with dark ink. Explicit so they never
   inherit an unreadable dark-on-dark or light-on-light combo from the
   active Plasma palette. */
#PaperDoc, #PaperEdit {{
    background: #ffffff;
    color: #2b2b33;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 12px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
"""


def make_header(title: str, subtitle: str = "") -> QWidget:
    """A gradient header band with a title and optional subtitle."""
    band = QFrame()
    band.setObjectName("HeaderBand")
    band.setFixedHeight(58 if subtitle else 46)
    lay = QVBoxLayout(band)
    lay.setContentsMargins(16, 8, 16, 8)
    lay.setSpacing(1)
    t = QLabel(title)
    t.setObjectName("HeaderTitle")
    lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("HeaderSubtitle")
        lay.addWidget(s)
    return band


# ---- Sticky-note (post-it) look for the capture window --------------------

# Paper palette
PAPER = "#fef08a"  # yellow-200, classic sticky
PAPER_EDGE = "#fde047"  # yellow-300 for the title strip
PAPER_INK = "#3f3a1e"  # dark warm ink for handwriting feel
PAPER_MUTED = "#8a7f4a"

POSTIT_STYLESHEET = f"""
#PostitRoot {{
    background: transparent;
}}
#Paper {{
    background: {PAPER};
    border: none;
    border-radius: 2px;
}}
/* Title strip at the top of the note, slightly darker */
#PostitTitle {{
    background: transparent;
    color: {PAPER_INK};
    border: none;
    font-size: 15px;
    font-weight: 700;
    padding: 4px 2px;
}}
#PostitTitle QLineEdit, QLineEdit#PostitTitle {{
    background: transparent;
    color: {PAPER_INK};
    border: none;
    border-bottom: 1px dashed {PAPER_MUTED};
    font-size: 15px;
    font-weight: 700;
    padding: 4px 2px;
}}
QLineEdit#PostitTitle::placeholder {{ color: {PAPER_MUTED}; }}

QPlainTextEdit#PostitBody {{
    background: transparent;
    color: {PAPER_INK};
    border: none;
    font-size: 13px;
    padding: 2px;
    selection-background-color: {PAPER_MUTED};
    selection-color: #ffffff;
}}
QPlainTextEdit#PostitBody::placeholder {{ color: {PAPER_MUTED}; }}

/* Slim footer bar inside the paper */
#PostitFooter QLabel {{ color: {PAPER_MUTED}; font-size: 11px; }}
#PostitFooter QToolButton {{
    background: transparent;
    color: {PAPER_INK};
    border: none;
    padding: 3px 6px;
    border-radius: 4px;
    font-size: 12px;
}}
#PostitFooter QToolButton:hover {{ background: rgba(0,0,0,0.08); }}
#PostitFooter QToolButton:disabled {{ color: {PAPER_MUTED}; }}
#PostitFooter QToolButton::menu-indicator {{ image: none; }}

/* Save/close chips */
QToolButton#PostitSave {{
    background: {PAPER_INK};
    color: {PAPER};
    border: none;
    border-radius: 5px;
    padding: 4px 12px;
    font-weight: 700;
    font-size: 12px;
}}
QToolButton#PostitSave:hover {{ background: #55502c; }}
"""
