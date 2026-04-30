import os
import tempfile

# ── SVG arrow for combo box (macOS compatibility) ────────────────────────────
_ARROW_SVG_PATH = os.path.join(tempfile.gettempdir(), "ossl_combo_arrow.svg")
_ARROW_SVG_URL = _ARROW_SVG_PATH.replace("\\", "/")
with open(_ARROW_SVG_PATH, "w") as _f:
    _f.write(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="6">'
        '<polygon points="0,0 10,0 5,6" fill="#8891a5"/>'
        '</svg>'
    )

# ── Color system ─────────────────────────────────────────────────────────────
C_BG          = "#f5f6f8"
C_CARD        = "#ffffff"
C_ACCENT      = "#4f6ef7"
C_ACCENT_HOV  = "#3d5ce5"
C_ACCENT_LIGHT = "#f0f2ff"
C_ACCENT_BORDER = "#d4daff"
C_TEXT        = "#1a1f36"
C_LABEL       = "#8891a5"
C_HINT        = "#b0b7c5"
C_BORDER      = "#ebedf2"
C_BORDER_HOV  = "#c5cad6"

C_OPTIMAL_BG    = "#e8faf0"
C_OPTIMAL_BORDER = "#8fe8b8"
C_OPTIMAL_TEXT  = "#15803d"
C_FEASIBLE_BG   = "#fef9ee"
C_FEASIBLE_BORDER = "#fad275"
C_FEASIBLE_TEXT = "#a16207"
C_DANGER        = "#dc2626"
C_DANGER_BORDER = "#fecaca"

C_CHIP_BG     = "#f0f2ff"
C_CHIP_BORDER = "#d4daff"
C_CHIP_TEXT   = "#3b55c9"

C_PARAM_BG    = "#f8f9fc"

# ── Font families ────────────────────────────────────────────────────────────
FONT_MONO = "'SF Mono', 'Menlo', 'Consolas', monospace"
FONT_SANS = "system-ui, -apple-system, 'Segoe UI', sans-serif"

# ── Limits ───────────────────────────────────────────────────────────────────
MAX_DISPLAYED_GROUPS = 5000
RESULTS_PER_PAGE = 8

# ── Button styles ────────────────────────────────────────────────────────────
SS_SOLVE = (
    f"QPushButton{{background:{C_ACCENT};color:white;border:none;"
    f"font-family:{FONT_SANS};font-weight:600;font-size:13px;"
    f"padding:10px;border-radius:10px;}}"
    f"QPushButton:hover{{background:{C_ACCENT_HOV};}}"
    f"QPushButton:disabled{{background:#b0bbf0;color:rgba(255,255,255,0.6);}}"
)
SS_SAVE = (
    f"QPushButton{{background:{C_ACCENT_LIGHT};color:{C_ACCENT};"
    f"border:1px solid {C_ACCENT_BORDER};border-radius:8px;"
    f"font-family:{FONT_SANS};font-weight:600;font-size:13px;padding:8px 12px;}}"
    f"QPushButton:hover{{background:#e4e8ff;border-color:{C_ACCENT};}}"
    f"QPushButton:disabled{{opacity:0.5;}}"
)
SS_EXPORT = (
    f"QPushButton{{background:{C_CARD};color:#64748b;"
    f"border:1px solid {C_BORDER};border-radius:8px;"
    f"font-family:{FONT_SANS};font-weight:600;font-size:13px;padding:8px 12px;}}"
    f"QPushButton:hover{{background:#f8f9fc;border-color:{C_BORDER_HOV};}}"
    f"QPushButton:disabled{{opacity:0.5;}}"
)
SS_CLEAR = (
    f"QPushButton{{background:{C_CARD};color:{C_DANGER};"
    f"border:1px solid {C_DANGER_BORDER};border-radius:8px;"
    f"font-family:{FONT_SANS};font-weight:600;font-size:13px;padding:8px 12px;}}"
    f"QPushButton:hover{{background:#fef2f2;border-color:{C_DANGER};}}"
)
SS_ACCENT_SM = (
    f"QPushButton{{background:{C_ACCENT};color:white;border:none;"
    f"font-family:{FONT_SANS};font-weight:600;font-size:12px;"
    f"padding:6px 14px;border-radius:8px;}}"
    f"QPushButton:hover{{background:{C_ACCENT_HOV};}}"
)
SS_DANGER_SM = (
    f"QPushButton{{background:{C_CARD};color:{C_DANGER};"
    f"border:1px solid {C_DANGER_BORDER};border-radius:8px;"
    f"font-family:{FONT_SANS};font-size:12px;padding:6px 14px;}}"
    f"QPushButton:hover{{background:#fef2f2;}}"
)

# ── Section title style ──────────────────────────────────────────────────────
SS_SECTION_TITLE = (
    f"color:{C_LABEL}; font-family:{FONT_SANS}; font-size:10px;"
    f"font-weight:600; letter-spacing:1.2px;"
)

# ── Application-wide QSS ─────────────────────────────────────────────────────
APP_STYLE = f"""
QMainWindow, QDialog {{
    background: {C_BG};
    font-family: {FONT_SANS};
}}
QLabel {{
    color: {C_TEXT};
    font-family: {FONT_SANS};
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #CDD1E0;
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
}}
QScrollBar::handle:horizontal {{
    background: #CDD1E0;
    border-radius: 3px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QStatusBar {{
    background: {C_CARD};
    border-top: 1px solid {C_BORDER};
    font-size: 11px;
    color: {C_LABEL};
}}
QComboBox {{
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 4px 8px;
    background: {C_CARD};
    color: {C_TEXT};
    font-family: {FONT_MONO};
    font-size: 14px;
    font-weight: 700;
    min-height: 28px;
}}
QComboBox:focus {{
    border-color: {C_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: url("{_ARROW_SVG_URL}");
    width: 10px;
    height: 6px;
}}
QComboBox QAbstractItemView {{
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    background: {C_CARD};
    color: {C_TEXT};
    padding: 4px;
    outline: none;
    font-family: {FONT_MONO};
    font-size: 14px;
    font-weight: 700;
    selection-background-color: {C_ACCENT};
    selection-color: white;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 12px;
    border-radius: 4px;
    min-height: 24px;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {C_ACCENT_LIGHT};
    color: {C_ACCENT};
}}
"""
