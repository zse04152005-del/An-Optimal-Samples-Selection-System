import random
import math
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QMessageBox,
    QComboBox, QScrollArea, QFrame, QSizePolicy, QShortcut
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence

from gui.styles import (
    C_ACCENT, C_ACCENT_HOV, C_ACCENT_LIGHT, C_ACCENT_BORDER,
    C_BG, C_CARD, C_BORDER, C_BORDER_HOV, C_TEXT, C_LABEL, C_HINT,
    C_PARAM_BG, C_DANGER, C_DANGER_BORDER,
    C_OPTIMAL_BG, C_OPTIMAL_BORDER, C_OPTIMAL_TEXT,
    C_FEASIBLE_BG, C_FEASIBLE_BORDER, C_FEASIBLE_TEXT,
    C_CHIP_BG, C_CHIP_BORDER, C_CHIP_TEXT,
    FONT_MONO, FONT_SANS,
    SS_SOLVE, SS_SAVE, SS_EXPORT, SS_CLEAR,
    SS_ACCENT_SM,
    _ARROW_SVG_URL, MAX_DISPLAYED_GROUPS, RESULTS_PER_PAGE,
    SS_SECTION_TITLE,
)
from gui.widgets.progress_bar import EnhancedProgressBar


class ComputationTab(QWidget):

    solve_requested = pyqtSignal()
    verify_requested = pyqtSignal()
    save_requested = pyqtSignal()
    export_requested = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_samples = []
        self.current_results = []
        self._results_page = 0
        self._param_cards: dict[str, dict] = {}
        self.setStyleSheet(f"background:{C_BG};")
        self._init_layout()
        self._init_shortcuts()

    # ══════════════════════════════════════════════════════════════════════════
    # LAYOUT
    # ══════════════════════════════════════════════════════════════════════════

    def _init_layout(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ──── LEFT COLUMN (200px) ────────────────────────────────────────────
        left_panel = QWidget()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet(
            f"background:{C_CARD}; border-right:1px solid {C_BORDER};")
        lv = QVBoxLayout(left_panel)
        lv.setContentsMargins(16, 16, 16, 16)
        lv.setSpacing(6)

        lv.addWidget(self._section_title("PARAMETERS"))

        self.m_combo = self._make_param_combo(45, 54, 45)
        self.n_combo = self._make_param_combo(7, 25, 9)
        self.k_combo = self._make_param_combo(4, 7, 6)
        self.j_combo = self._make_param_combo(3, 7, 4)
        self.s_combo = self._make_param_combo(3, 7, 4)
        self.r_combo = self._make_param_combo(1, 20, 1)
        self.time_combo = self._make_time_limit_combo()

        lv.addWidget(self._param_card("M", "total", "pool size", self.m_combo, 45, 54))
        lv.addWidget(self._param_card("N", "selected", "samples", self.n_combo, 7, 25))
        lv.addWidget(self._param_card("K", "group", "group size", self.k_combo, 4, 7))
        lv.addWidget(self._param_card("J", "subset", "subset size", self.j_combo, 3, 7))

        # S card (special)
        self._s_card = self._s_param_card()
        lv.addWidget(self._s_card)

        # R (rounds) - small
        lv.addWidget(self._param_card("R", "rounds", "iterations", self.r_combo, 1, 20))
        lv.addWidget(self._param_card("T", "time limit", "seconds", self.time_combo, 5, 3600))

        lv.addStretch()

        # Solve button at bottom
        self.solve_btn = QPushButton("Solve")
        self.solve_btn.setStyleSheet(SS_SOLVE)
        self.solve_btn.setCursor(Qt.PointingHandCursor)
        self.solve_btn.clicked.connect(self.solve_requested.emit)
        lv.addWidget(self.solve_btn)

        # Progress bar below solve
        self.progress_bar = EnhancedProgressBar()
        lv.addWidget(self.progress_bar)

        self.k_combo.currentTextChanged.connect(self._update_constraints)
        self.j_combo.currentTextChanged.connect(self._update_constraints)
        self.s_combo.currentTextChanged.connect(self._update_constraints)
        self.j_combo.currentTextChanged.connect(self._update_s_description)
        self.s_combo.currentTextChanged.connect(self._update_s_description)
        self.m_combo.currentTextChanged.connect(self._on_m_changed)
        self.n_combo.currentTextChanged.connect(self._on_n_changed)
        self.m_combo.currentTextChanged.connect(lambda _: self._validate_params())
        self.n_combo.currentTextChanged.connect(lambda _: self._validate_params())
        self.k_combo.currentTextChanged.connect(lambda _: self._validate_params())
        self.time_combo.currentTextChanged.connect(lambda _: self._validate_params())

        outer.addWidget(left_panel)

        # ──── CENTER COLUMN (flex) ───────────────────────────────────────────
        center = QWidget()
        center.setStyleSheet(f"background:{C_BG};")
        cv = QVBoxLayout(center)
        cv.setContentsMargins(20, 16, 20, 16)
        cv.setSpacing(12)

        # Sample pool header
        pool_hdr = QHBoxLayout()
        pool_hdr.addWidget(self._section_title("SAMPLE POOL"))
        pool_hdr.addStretch()

        # Mode toggle pill
        self._mode_pill = QWidget()
        self._mode_pill.setFixedHeight(30)
        self._mode_pill.setStyleSheet(
            f"background:{C_BORDER}; border-radius:8px;")
        pill_ly = QHBoxLayout(self._mode_pill)
        pill_ly.setContentsMargins(3, 3, 3, 3)
        pill_ly.setSpacing(2)
        self._random_btn = QPushButton("Random")
        self._manual_btn = QPushButton("Manual")
        self._random_btn.setFixedHeight(24)
        self._manual_btn.setFixedHeight(24)
        self._random_btn.setCursor(Qt.PointingHandCursor)
        self._manual_btn.setCursor(Qt.PointingHandCursor)
        self._random_btn.clicked.connect(lambda: self._set_mode("random"))
        self._manual_btn.clicked.connect(lambda: self._set_mode("manual"))
        pill_ly.addWidget(self._random_btn)
        pill_ly.addWidget(self._manual_btn)
        self._mode = "random"
        self._refresh_mode_pills()
        pool_hdr.addWidget(self._mode_pill)

        # Count badge
        self._pool_count = QLabel("0 / 45")
        self._pool_count.setStyleSheet(
            f"background:{C_ACCENT_LIGHT}; color:{C_ACCENT}; font-family:{FONT_MONO};"
            f"font-size:11px; font-weight:700; padding:3px 8px; border-radius:6px;")
        pool_hdr.addWidget(self._pool_count)

        # Generate button
        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setStyleSheet(
            f"QPushButton{{background:{C_ACCENT_LIGHT};color:{C_ACCENT};"
            f"border:1px solid {C_ACCENT_BORDER};border-radius:6px;"
            f"font-size:11px;font-weight:600;padding:3px 10px;}}"
            f"QPushButton:hover{{background:#e4e8ff;}}")
        self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.clicked.connect(self._generate_samples)
        pool_hdr.addWidget(self.generate_btn)

        cv.addLayout(pool_hdr)

        # Pool grid
        pool_scroll = QScrollArea()
        pool_scroll.setWidgetResizable(True)
        pool_scroll.setFixedHeight(200)
        pool_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pool_scroll.setStyleSheet("background:transparent; border:none;")
        self._pool_widget = QWidget()
        self._pool_widget.setStyleSheet("background:transparent;")
        self._pool_grid = QGridLayout(self._pool_widget)
        self._pool_grid.setSpacing(4)
        self._pool_grid.setContentsMargins(0, 0, 0, 0)
        pool_scroll.setWidget(self._pool_widget)
        cv.addWidget(pool_scroll)
        self._pool_buttons: dict[int, QPushButton] = {}
        self._pool_selected: set[int] = set()

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none;")
        cv.addWidget(sep)

        # Results header
        res_hdr = QHBoxLayout()
        res_hdr.addWidget(self._section_title("RESULT GROUPS"))
        res_hdr.addStretch()
        self._results_count_lbl = QLabel("")
        self._results_count_lbl.setStyleSheet(
            f"color:{C_HINT}; font-size:11px;")
        res_hdr.addWidget(self._results_count_lbl)
        cv.addLayout(res_hdr)

        # Results scroll area (card grid)
        self._results_scroll = QScrollArea()
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setStyleSheet("background:transparent; border:none;")
        self._results_container = QWidget()
        self._results_container.setStyleSheet("background:transparent;")
        self._results_grid = QGridLayout(self._results_container)
        self._results_grid.setSpacing(8)
        self._results_grid.setContentsMargins(0, 0, 0, 0)
        self._results_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._results_scroll.setWidget(self._results_container)

        # Placeholder
        self._results_placeholder = QLabel(
            "Set parameters, generate samples,\nthen press Solve.")
        self._results_placeholder.setAlignment(Qt.AlignCenter)
        self._results_placeholder.setStyleSheet(
            f"color:{C_HINT}; font-size:13px; padding:40px;")

        cv.addWidget(self._results_placeholder)
        cv.addWidget(self._results_scroll, stretch=1)
        self._results_scroll.setVisible(False)

        # Pagination
        self._pager = QWidget()
        self._pager.setVisible(False)
        pager_ly = QHBoxLayout(self._pager)
        pager_ly.setContentsMargins(0, 4, 0, 0)
        pager_ly.setSpacing(6)
        self._page_prev = QPushButton("<")
        self._page_prev.setFixedSize(28, 28)
        self._page_prev.setStyleSheet(
            f"QPushButton{{background:{C_CARD};border:1px solid {C_BORDER};"
            f"border-radius:6px;font-size:12px;color:{C_TEXT};}}"
            f"QPushButton:hover{{background:#f0f2f5;}}")
        self._page_prev.clicked.connect(lambda: self._change_page(-1))
        self._page_next = QPushButton(">")
        self._page_next.setFixedSize(28, 28)
        self._page_next.setStyleSheet(self._page_prev.styleSheet())
        self._page_next.clicked.connect(lambda: self._change_page(1))
        self._page_dots = QWidget()
        self._page_dots_ly = QHBoxLayout(self._page_dots)
        self._page_dots_ly.setContentsMargins(0, 0, 0, 0)
        self._page_dots_ly.setSpacing(4)
        self._page_info = QLabel("")
        self._page_info.setStyleSheet(f"color:{C_HINT}; font-size:11px;")
        pager_ly.addWidget(self._page_prev)
        pager_ly.addWidget(self._page_dots)
        pager_ly.addWidget(self._page_next)
        pager_ly.addStretch()
        pager_ly.addWidget(self._page_info)
        cv.addWidget(self._pager)

        outer.addWidget(center, stretch=1)

        # ──── RIGHT COLUMN (280px) ───────────────────────────────────────────
        right_panel = QWidget()
        right_panel.setFixedWidth(280)
        right_panel.setStyleSheet(
            f"background:{C_CARD}; border-left:1px solid {C_BORDER};")
        rv = QVBoxLayout(right_panel)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(10)

        rv.addWidget(self._section_title("SOLUTION"))

        # Big number card
        self._big_num_card = QWidget()
        self._big_num_card.setStyleSheet(
            f"background:{C_PARAM_BG}; border:1px solid {C_BORDER}; border-radius:12px;")
        bn_ly = QVBoxLayout(self._big_num_card)
        bn_ly.setContentsMargins(16, 16, 16, 16)
        bn_ly.setAlignment(Qt.AlignCenter)
        self._big_num = QLabel("--")
        self._big_num.setAlignment(Qt.AlignCenter)
        self._big_num.setStyleSheet(
            f"background:transparent; color:{C_TEXT}; font-family:{FONT_MONO};"
            f"font-size:36px; font-weight:800;")
        self._big_num_sub = QLabel("groups found")
        self._big_num_sub.setAlignment(Qt.AlignCenter)
        self._big_num_sub.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:11px;")
        bn_ly.addWidget(self._big_num)
        bn_ly.addWidget(self._big_num_sub)
        rv.addWidget(self._big_num_card)

        # Status badge
        self._status_badge = QWidget()
        self._status_badge.setVisible(False)
        sb_ly = QHBoxLayout(self._status_badge)
        sb_ly.setContentsMargins(12, 10, 12, 10)
        sb_ly.setAlignment(Qt.AlignCenter)
        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        self._status_text = QLabel("")
        self._status_text.setStyleSheet(
            f"background:transparent; font-size:14px; font-weight:600;")
        sb_ly.addWidget(self._status_dot)
        sb_ly.addWidget(self._status_text)
        rv.addWidget(self._status_badge)

        # Mini stats (2x grid)
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)
        self._stat_time = self._mini_stat("--", "solve time")
        self._stat_candidates = self._mini_stat("--", "candidates")
        stats_grid.addWidget(self._stat_time, 0, 0)
        stats_grid.addWidget(self._stat_candidates, 0, 1)
        rv.addLayout(stats_grid)

        # Run config
        rv.addWidget(self._section_title("RUN CONFIG"))
        self._config_card = QWidget()
        self._config_card.setStyleSheet(
            f"background:{C_PARAM_BG}; border:1px solid {C_BORDER}; border-radius:10px;")
        self._config_ly = QVBoxLayout(self._config_card)
        self._config_ly.setContentsMargins(12, 10, 12, 10)
        self._config_ly.setSpacing(0)
        self._config_rows = {}
        for key in ("Pool", "Candidates", "Constraint", "Solver", "Time", "Gap"):
            row = self._config_row(key, "--")
            self._config_rows[key] = row
            self._config_ly.addWidget(row)
        rv.addWidget(self._config_card)

        # Verification
        rv.addWidget(self._section_title("VERIFICATION"))
        self._verification_card = QWidget()
        self._verification_card.setStyleSheet(
            f"background:{C_PARAM_BG}; border:1px solid {C_BORDER}; border-radius:10px;")
        self._verification_ly = QVBoxLayout(self._verification_card)
        self._verification_ly.setContentsMargins(12, 10, 12, 10)
        self._verification_ly.setSpacing(0)

        self._verification_status = QLabel("Not checked")
        self._verification_status.setWordWrap(True)
        self._verification_status.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:13px; font-weight:700;")
        self._verification_ly.addWidget(self._verification_status)

        self._verification_rows = {}
        for key in ("Coverage", "Groups", "Issues", "Optimality"):
            row = self._verification_row(key, "--")
            self._verification_rows[key] = row
            self._verification_ly.addWidget(row)
        rv.addWidget(self._verification_card)

        rv.addStretch()

        # Actions
        rv.addWidget(self._section_title("ACTIONS"))
        self.verify_btn = QPushButton("Verify")
        self.verify_btn.setStyleSheet(SS_ACCENT_SM)
        self.verify_btn.setCursor(Qt.PointingHandCursor)
        self.verify_btn.clicked.connect(self.verify_requested.emit)
        self.verify_btn.setEnabled(False)
        rv.addWidget(self.verify_btn)

        act_row = QHBoxLayout()
        act_row.setSpacing(8)
        self.save_btn = QPushButton("Save")
        self.save_btn.setStyleSheet(SS_SAVE)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_requested.emit)
        self.save_btn.setEnabled(False)
        self.print_btn = QPushButton("Export")
        self.print_btn.setStyleSheet(SS_EXPORT)
        self.print_btn.setCursor(Qt.PointingHandCursor)
        self.print_btn.clicked.connect(self.export_requested.emit)
        self.print_btn.setEnabled(False)
        act_row.addWidget(self.save_btn, stretch=1)
        act_row.addWidget(self.print_btn, stretch=1)
        rv.addLayout(act_row)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(SS_CLEAR)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        rv.addWidget(self.clear_btn)

        outer.addWidget(right_panel)

        self._rebuild_pool()

    # ══════════════════════════════════════════════════════════════════════════
    # WIDGET FACTORIES
    # ══════════════════════════════════════════════════════════════════════════

    def _section_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(SS_SECTION_TITLE)
        return lbl

    def _param_card(self, key, name, hint_text, combo, lo, hi):
        card = QWidget()
        card.setStyleSheet(
            f"background:{C_PARAM_BG}; border:1px solid {C_BORDER}; border-radius:10px;")
        ly = QHBoxLayout(card)
        ly.setContentsMargins(10, 8, 10, 8)

        left = QVBoxLayout()
        left.setSpacing(1)
        label = QLabel(f"{key}  {name}")
        label.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:11px; font-weight:500;")
        hint = QLabel(f"{hint_text} {lo}-{hi}")
        hint.setStyleSheet(
            f"background:transparent; color:{C_HINT}; font-size:10px;")
        left.addWidget(label)
        left.addWidget(hint)
        ly.addLayout(left, stretch=1)

        combo.setFixedWidth(60)
        ly.addWidget(combo)

        self._param_cards[key] = {
            'card': card, 'hint': hint, 'default_hint': f"{hint_text} {lo}-{hi}",
        }
        return card

    def _s_param_card(self):
        card = QWidget()
        card.setStyleSheet(
            f"background:{C_ACCENT_LIGHT}; border:1px solid {C_ACCENT_BORDER}; border-radius:10px;")
        ly = QVBoxLayout(card)
        ly.setContentsMargins(10, 8, 10, 8)
        ly.setSpacing(4)

        top = QHBoxLayout()
        label = QLabel("S  coverage")
        label.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:11px; font-weight:500;")
        top.addWidget(label)
        top.addStretch()
        self.s_combo.setFixedWidth(60)
        top.addWidget(self.s_combo)
        ly.addLayout(top)

        self._s_desc = QLabel("")
        self._s_desc.setWordWrap(True)
        self._s_desc.setStyleSheet(
            f"background:transparent; color:{C_ACCENT}; font-family:{FONT_SANS};"
            f"font-size:13px; font-weight:600;")
        ly.addWidget(self._s_desc)
        self._update_s_description()

        hint = QLabel("threshold 3-7")
        hint.setStyleSheet(
            f"background:transparent; color:{C_HINT}; font-size:10px;")
        ly.addWidget(hint)

        self._param_cards['S'] = {
            'card': card, 'hint': hint, 'default_hint': "threshold 3-7",
        }
        return card

    def _mini_stat(self, value, label):
        w = QWidget()
        w.setStyleSheet(
            f"background:{C_PARAM_BG}; border-radius:10px;")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(12, 10, 12, 10)
        ly.setAlignment(Qt.AlignCenter)
        val = QLabel(value)
        val.setObjectName("miniVal")
        val.setAlignment(Qt.AlignCenter)
        val.setStyleSheet(
            f"background:transparent; color:{C_TEXT}; font-family:{FONT_MONO};"
            f"font-size:16px; font-weight:700;")
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"background:transparent; color:{C_HINT}; font-size:10px;")
        ly.addWidget(val)
        ly.addWidget(lbl)
        return w

    def _config_row(self, key, value):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        ly = QHBoxLayout(w)
        ly.setContentsMargins(0, 6, 0, 6)
        k = QLabel(key)
        k.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:12px;")
        v = QLabel(value)
        v.setObjectName("cfgVal")
        v.setAlignment(Qt.AlignRight)
        v.setStyleSheet(
            f"background:transparent; color:{C_TEXT}; font-family:{FONT_MONO};"
            f"font-size:12px; font-weight:600;")
        ly.addWidget(k)
        ly.addStretch()
        ly.addWidget(v)
        return w

    def _verification_row(self, key, value):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        ly = QHBoxLayout(w)
        ly.setContentsMargins(0, 5, 0, 5)
        k = QLabel(key)
        k.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:11px;")
        v = QLabel(value)
        v.setObjectName("verifyVal")
        v.setAlignment(Qt.AlignRight)
        v.setStyleSheet(
            f"background:transparent; color:{C_TEXT}; font-family:{FONT_MONO};"
            f"font-size:11px; font-weight:600;")
        ly.addWidget(k)
        ly.addStretch()
        ly.addWidget(v)
        return w

    def _make_param_combo(self, lo, hi, default):
        c = QComboBox()
        c.setEditable(False)
        for v in range(lo, hi + 1):
            c.addItem(str(v))
        idx = c.findText(str(default))
        if idx >= 0:
            c.setCurrentIndex(idx)
        c.currentTextChanged.connect(lambda _: self._update_param_buttons_state())
        return c

    def _make_time_limit_combo(self):
        c = QComboBox()
        c.setEditable(True)
        c.setInsertPolicy(QComboBox.NoInsert)
        for value in (30, 70, 120, 300, 600):
            c.addItem(str(value))
        idx = c.findText("70")
        if idx >= 0:
            c.setCurrentIndex(idx)
        if c.lineEdit():
            c.lineEdit().setAlignment(Qt.AlignRight)
            c.lineEdit().setToolTip("Enter a time limit in seconds, from 5 to 3600.")
        return c

    def _result_card(self, idx, group):
        card = QWidget()
        card.setStyleSheet(
            f"QWidget{{background:{C_CARD}; border:1px solid {C_BORDER}; border-radius:10px;}}"
            f"QWidget:hover{{border-color:{C_BORDER_HOV};}}")
        ly = QVBoxLayout(card)
        ly.setContentsMargins(10, 8, 10, 8)
        ly.setSpacing(6)

        num = QLabel(f"#{idx:02d}")
        num.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-family:{FONT_MONO};"
            f"font-size:11px; font-weight:700;")
        ly.addWidget(num)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        for v in group:
            chip = QLabel(str(v))
            chip.setFixedSize(30, 26)
            chip.setAlignment(Qt.AlignCenter)
            chip.setStyleSheet(
                f"background:{C_CHIP_BG}; border:1px solid {C_CHIP_BORDER};"
                f"color:{C_CHIP_TEXT}; font-family:{FONT_MONO};"
                f"font-size:12px; font-weight:700; border-radius:6px;")
            chips.addWidget(chip)
        chips.addStretch()
        ly.addLayout(chips)
        return card

    # ══════════════════════════════════════════════════════════════════════════
    # MODE TOGGLE
    # ══════════════════════════════════════════════════════════════════════════

    def _set_mode(self, mode):
        self._mode = mode
        self._refresh_mode_pills()

    def _refresh_mode_pills(self):
        active = (
            f"QPushButton{{background:{C_CARD};color:{C_TEXT};border:none;"
            f"border-radius:6px;font-size:11px;font-weight:600;padding:2px 10px;}}")
        inactive = (
            f"QPushButton{{background:transparent;color:{C_LABEL};border:none;"
            f"border-radius:6px;font-size:11px;font-weight:500;padding:2px 10px;}}"
            f"QPushButton:hover{{color:{C_TEXT};}}")
        if self._mode == "random":
            self._random_btn.setStyleSheet(active)
            self._manual_btn.setStyleSheet(inactive)
        else:
            self._random_btn.setStyleSheet(inactive)
            self._manual_btn.setStyleSheet(active)

    # ══════════════════════════════════════════════════════════════════════════
    # SAMPLE POOL
    # ══════════════════════════════════════════════════════════════════════════

    def _rebuild_pool(self):
        try:
            m = int(self.m_combo.currentText())
        except ValueError:
            return
        to_remove = [num for num in list(self._pool_buttons) if num > m]
        for num in to_remove:
            btn = self._pool_buttons.pop(num)
            self._pool_grid.removeWidget(btn)
            btn.deleteLater()
        self._pool_selected.difference_update(to_remove)

        cols = 10
        for num in range(1, m + 1):
            if num not in self._pool_buttons:
                btn = QPushButton(str(num))
                btn.setFixedSize(38, 38)
                btn.setCheckable(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda _, n=num: self._toggle_pool(n))
                self._pool_buttons[num] = btn
                row, col = divmod(num - 1, cols)
                self._pool_grid.addWidget(btn, row, col)
        self._refresh_pool_display()

    def _toggle_pool(self, num):
        if self._mode != "manual":
            return
        n = self._safe_int(self.n_combo, 9)
        if num in self._pool_selected:
            self._pool_selected.discard(num)
        else:
            if len(self._pool_selected) >= n:
                QMessageBox.information(
                    self, "Limit reached",
                    f"You can only select {n} samples (n = {n}).")
                return
            self._pool_selected.add(num)
        self._refresh_pool_display()

    def _refresh_pool_display(self):
        n = self._safe_int(self.n_combo, 9)
        m = self._safe_int(self.m_combo, 45)
        self._pool_count.setText(f"{len(self._pool_selected)} / {m}")

        for num, btn in self._pool_buttons.items():
            active = num in self._pool_selected
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    f"QPushButton{{background:{C_ACCENT};color:white;"
                    f"border:1.5px solid {C_ACCENT};border-radius:8px;"
                    f"font-family:{FONT_MONO};font-size:12px;font-weight:600;padding:0px;}}"
                    f"QPushButton:hover{{background:{C_ACCENT_HOV};}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:{C_CARD};color:{C_BORDER_HOV};"
                    f"border:1.5px solid {C_BORDER};border-radius:8px;"
                    f"font-family:{FONT_MONO};font-size:12px;font-weight:600;padding:0px;}}"
                    f"QPushButton:hover{{border-color:{C_BORDER_HOV};color:{C_TEXT};}}")

    # ══════════════════════════════════════════════════════════════════════════
    # RESULTS DISPLAY + PAGINATION
    # ══════════════════════════════════════════════════════════════════════════

    def _render_results_page(self):
        while self._results_grid.count():
            item = self._results_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(self.current_results)
        if total == 0:
            return

        start = self._results_page * RESULTS_PER_PAGE
        end = min(start + RESULTS_PER_PAGE, total)
        page_items = self.current_results[start:end]

        COLS = 2
        for i, group in enumerate(page_items):
            card = self._result_card(start + i + 1, group)
            self._results_grid.addWidget(card, i // COLS, i % COLS)

        total_pages = math.ceil(total / RESULTS_PER_PAGE)
        self._page_prev.setEnabled(self._results_page > 0)
        self._page_next.setEnabled(self._results_page < total_pages - 1)
        self._page_info.setText(f"{start + 1}-{end} of {total}")
        self._render_page_dots(total_pages)

    def _render_page_dots(self, total_pages):
        while self._page_dots_ly.count():
            item = self._page_dots_ly.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i in range(min(total_pages, 10)):
            dot = QWidget()
            if i == self._results_page:
                dot.setFixedSize(20, 8)
                dot.setStyleSheet(
                    f"background:{C_ACCENT}; border-radius:4px;")
            else:
                dot.setFixedSize(8, 8)
                dot.setStyleSheet(
                    f"background:#dfe2e8; border-radius:4px;")
            self._page_dots_ly.addWidget(dot)

    def _change_page(self, delta):
        total_pages = math.ceil(len(self.current_results) / RESULTS_PER_PAGE)
        new_page = self._results_page + delta
        if 0 <= new_page < total_pages:
            self._results_page = new_page
            self._render_results_page()

    # ══════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════════════

    def get_params(self):
        return {
            'm': self._safe_int(self.m_combo, 45),
            'n': self._safe_int(self.n_combo, 9),
            'k': self._safe_int(self.k_combo, 6),
            'j': self._safe_int(self.j_combo, 4),
            's': self._safe_int(self.s_combo, 4),
            'r': self._safe_int(self.r_combo, 1),
            'time_limit': self._time_limit_seconds(),
        }

    def get_samples(self):
        return list(self.current_samples)

    def set_samples(self, samples):
        self.current_samples = list(samples)
        self._pool_selected = set(samples)
        self._refresh_pool_display()

    def show_results(self, result, solve_time, method, status, stats=None):
        self.current_results = result
        self._results_page = 0

        # Big number
        self._big_num.setText(str(len(result)))

        # Status badge
        self._set_status_badge(status)

        # Time formatting
        if solve_time < 1.0:
            time_str = f"{solve_time * 1000:.0f}ms"
        else:
            time_str = f"{solve_time:.1f}s"
        self._stat_time.findChild(QLabel, "miniVal").setText(time_str)

        # Candidates
        p = self.get_params()
        try:
            candidates = math.comb(p['n'], p['k'])
        except (ValueError, TypeError):
            candidates = 0
        self._stat_candidates.findChild(QLabel, "miniVal").setText(str(candidates))

        # Run config
        self._update_config_value("Pool", f"C({p['m']}, {p['n']})")
        self._update_config_value("Candidates", f"C({p['n']},{p['k']})={candidates}")
        try:
            constraints = math.comb(p['n'], p['j'])
        except (ValueError, TypeError):
            constraints = 0
        self._update_config_value("Constraint", f"C({p['n']},{p['j']})={constraints}")
        solver_name = method.split("(")[0].strip() if method else "ILP"
        self._update_config_value("Solver", solver_name[:12])
        self._update_config_value("Time", f"{p['time_limit']}s")

        best_bound = stats.get('best_bound') if stats else None
        if best_bound is not None and best_bound > 0 and len(result) > 0:
            gap = (len(result) - best_bound) / len(result) * 100
            gap_str = f"{gap:.1f}%"
        elif status == "OPTIMAL":
            gap_str = "0.0%"
        else:
            gap_str = "N/A"
        self._update_config_value("Gap", gap_str)
        self._set_verification_pending(has_results=bool(result))

        # Results cards
        self._results_placeholder.setVisible(False)
        self._results_scroll.setVisible(True)
        self._pager.setVisible(len(result) > RESULTS_PER_PAGE)
        self._results_count_lbl.setText(f"{len(result)} groups")
        self._render_results_page()

        self.save_btn.setEnabled(True)
        self.print_btn.setEnabled(True)

    def clear_results(self):
        self.current_samples = []
        self.current_results = []
        self._pool_selected.clear()
        self._refresh_pool_display()

        while self._results_grid.count():
            item = self._results_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._results_placeholder.setVisible(True)
        self._results_scroll.setVisible(False)
        self._pager.setVisible(False)
        self._results_count_lbl.setText("")
        self._big_num.setText("--")
        self._big_num_sub.setText("groups found")
        self._status_badge.setVisible(False)
        self._stat_time.findChild(QLabel, "miniVal").setText("--")
        self._stat_candidates.findChild(QLabel, "miniVal").setText("--")
        for key in self._config_rows:
            self._update_config_value(key, "--")
        self._set_verification_pending(has_results=False)
        self.verify_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.print_btn.setEnabled(False)

    def start_progress(self, budget_ms):
        self.solve_btn.setEnabled(False)
        self.solve_btn.setText("Solving...")
        self.verify_btn.setEnabled(False)
        self.progress_bar.start(budget_ms)

    def stop_progress(self):
        self.progress_bar.stop()
        self.solve_btn.setEnabled(True)
        self.solve_btn.setText("Solve")

    def set_round_info(self, current, total, best_size):
        self.progress_bar.set_round_info(current, total, best_size)

    def set_buttons_enabled(self, enabled):
        self.solve_btn.setEnabled(enabled)

    # ══════════════════════════════════════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _set_status_badge(self, status):
        self._status_badge.setVisible(True)
        if status == "OPTIMAL":
            bg, border, text = C_OPTIMAL_BG, C_OPTIMAL_BORDER, C_OPTIMAL_TEXT
        elif "FEASIBLE" in status:
            bg, border, text = C_FEASIBLE_BG, C_FEASIBLE_BORDER, C_FEASIBLE_TEXT
        else:
            bg, border, text = C_PARAM_BG, C_BORDER, C_LABEL
        self._status_badge.setStyleSheet(
            f"background:{bg}; border:1.5px solid {border}; border-radius:12px;")
        self._status_dot.setStyleSheet(
            f"background:{text}; border-radius:4px;")
        self._status_text.setStyleSheet(
            f"background:transparent; color:{text}; font-size:14px; font-weight:600;")
        self._status_text.setText(status)

    def _update_config_value(self, key, value):
        row = self._config_rows.get(key)
        if row:
            val_lbl = row.findChild(QLabel, "cfgVal")
            if val_lbl:
                val_lbl.setText(value)

    def _update_verification_value(self, key, value, tooltip=""):
        row = self._verification_rows.get(key)
        if row:
            val_lbl = row.findChild(QLabel, "verifyVal")
            if val_lbl:
                val_lbl.setText(value)
                val_lbl.setToolTip(tooltip)

    def _set_verification_pending(self, has_results):
        self._verification_card.setStyleSheet(
            f"background:{C_PARAM_BG}; border:1px solid {C_BORDER}; border-radius:10px;")
        self._verification_status.setText("Not checked")
        self._verification_status.setToolTip("")
        self._verification_status.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:13px; font-weight:700;")
        for key in self._verification_rows:
            self._update_verification_value(key, "--")
        self.verify_btn.setEnabled(has_results)

    def show_verification(self, report, solver_status, best_bound=None):
        if report.get("is_valid"):
            bg, border, text = C_OPTIMAL_BG, C_OPTIMAL_BORDER, C_OPTIMAL_TEXT
            title = "Passed"
        elif report.get("covers_all"):
            bg, border, text = C_FEASIBLE_BG, C_FEASIBLE_BORDER, C_FEASIBLE_TEXT
            title = "Needs review"
        else:
            bg, border, text = "#fef2f2", C_DANGER_BORDER, C_DANGER
            title = "Failed"

        self._verification_card.setStyleSheet(
            f"background:{bg}; border:1.5px solid {border}; border-radius:10px;")
        self._verification_status.setText(title)
        self._verification_status.setStyleSheet(
            f"background:transparent; color:{text}; font-size:13px; font-weight:800;")

        covered = report.get("covered_subsets", 0)
        total = report.get("total_subsets", 0)
        percent = report.get("coverage_percent", 0.0)
        self._update_verification_value(
            "Coverage", f"{covered:,}/{total:,}",
            f"{percent:.2f}% of required j-subsets are covered.")

        group_count = report.get("group_count", 0)
        unique_count = report.get("unique_group_count", 0)
        self._update_verification_value(
            "Groups", f"{unique_count:,}/{group_count:,}",
            "unique valid groups / displayed groups")

        issues = []
        if report.get("invalid_groups", 0):
            issues.append(f"{report['invalid_groups']} invalid")
        if report.get("duplicate_groups", 0):
            issues.append(f"{report['duplicate_groups']} duplicate")
        if report.get("uncovered_count", 0):
            issues.append(f"{report['uncovered_count']:,} uncovered")
        issue_text = ", ".join(issues) if issues else "None"

        detail_lines = [report.get("message", "")]
        invalid_examples = report.get("invalid_examples") or []
        if invalid_examples:
            detail_lines.append("Invalid groups: " + "; ".join(invalid_examples))
        uncovered_examples = report.get("uncovered_examples") or []
        if uncovered_examples:
            formatted = "; ".join(str(tuple(v)) for v in uncovered_examples)
            detail_lines.append("Uncovered examples: " + formatted)
        tooltip = "\n".join(line for line in detail_lines if line)
        self._verification_status.setToolTip(tooltip)
        self._update_verification_value("Issues", issue_text, tooltip)

        if solver_status == "OPTIMAL":
            optimality = "Proven"
        elif best_bound is not None and best_bound > 0 and group_count > 0:
            gap = (group_count - best_bound) / group_count * 100
            optimality = f"Gap {gap:.1f}%"
        elif "FEASIBLE" in (solver_status or ""):
            optimality = "Feasible"
        else:
            optimality = "Unknown"
        self._update_verification_value(
            "Optimality", optimality,
            "Coverage can be verified exactly. Minimum group count is proven only when status is OPTIMAL.")
        self.verify_btn.setEnabled(True)

    def _format_time(self, seconds):
        if seconds < 1.0:
            return f"{seconds * 1000:.0f}ms"
        return f"{seconds:.1f}s"

    def _update_constraints(self):
        try:
            k = int(self.k_combo.currentText())
            j = int(self.j_combo.currentText())
            s = int(self.s_combo.currentText())
        except ValueError:
            return
        if j > k:
            self.j_combo.setCurrentText(str(k))
        if s > j:
            self.s_combo.setCurrentText(str(j))
        self._validate_params()

    def _validate_params(self):
        m = self._safe_int(self.m_combo, 45)
        n = self._safe_int(self.n_combo, 9)
        k = self._safe_int(self.k_combo, 6)
        j = self._safe_int(self.j_combo, 4)
        s = self._safe_int(self.s_combo, 4)
        time_text = self.time_combo.currentText().strip()

        errors: dict[str, str] = {}
        if n > m:
            errors['N'] = f"n must be ≤ m ({m})"
        if k > n:
            errors['K'] = f"k must be ≤ n ({n})"
        if j > k:
            errors['J'] = f"j must be ≤ k ({k})"
        if s > j:
            errors['S'] = f"s must be ≤ j ({j})"

        try:
            time_limit = int(time_text)
        except ValueError:
            errors['T'] = "enter seconds"
        else:
            if not (5 <= time_limit <= 3600):
                errors['T'] = "seconds 5-3600"

        for key, info in self._param_cards.items():
            card, hint = info['card'], info['hint']
            if key in errors:
                if key == 'S':
                    card.setStyleSheet(
                        f"background:#fef2f2; border:1px solid {C_DANGER}; border-radius:10px;")
                else:
                    card.setStyleSheet(
                        f"background:#fef2f2; border:1px solid {C_DANGER}; border-radius:10px;")
                hint.setText(errors[key])
                hint.setStyleSheet(
                    f"background:transparent; color:{C_DANGER}; font-size:10px; font-weight:600;")
            else:
                if key == 'S':
                    card.setStyleSheet(
                        f"background:{C_ACCENT_LIGHT}; border:1px solid {C_ACCENT_BORDER}; border-radius:10px;")
                else:
                    card.setStyleSheet(
                        f"background:{C_PARAM_BG}; border:1px solid {C_BORDER}; border-radius:10px;")
                hint.setText(info['default_hint'])
                hint.setStyleSheet(
                    f"background:transparent; color:{C_HINT}; font-size:10px;")

        has_errors = bool(errors)
        self.solve_btn.setEnabled(not has_errors)
        self.generate_btn.setEnabled(not has_errors)

    def _update_s_description(self, *_):
        j = self._safe_int(self.j_combo, 4)
        s = self._safe_int(self.s_combo, 4)
        self._s_desc.setText(f"cover at least {s} from\nevery {j}-subset")

    def _on_m_changed(self, _):
        self._rebuild_pool()

    def _on_n_changed(self, _):
        self._refresh_pool_display()

    def _generate_samples(self):
        try:
            m = int(self.m_combo.currentText())
            n = int(self.n_combo.currentText())
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid m or n value.")
            return

        if self._mode == "random":
            chosen = sorted(random.sample(range(1, m + 1), n))
            self._pool_selected = set(chosen)
            self._refresh_pool_display()
            self.current_samples = chosen
        else:
            if len(self._pool_selected) != n:
                QMessageBox.warning(
                    self, "Selection mismatch",
                    f"Please select exactly {n} numbers from the pool "
                    f"(currently {len(self._pool_selected)} selected).")
                return
            self.current_samples = sorted(self._pool_selected)

    def _update_param_buttons_state(self):
        all_valid = all(
            combo.currentIndex() >= 0
            for combo in (self.m_combo, self.n_combo, self.k_combo,
                          self.j_combo, self.s_combo, self.r_combo)
        )
        self.generate_btn.setEnabled(all_valid)
        self.solve_btn.setEnabled(all_valid)

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Return"), self).activated.connect(
            self.solve_requested.emit)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            self.save_requested.emit)
        QShortcut(QKeySequence("Escape"), self).activated.connect(
            self.clear_requested.emit)

    @staticmethod
    def _safe_int(combo, default):
        try:
            return int(combo.currentText())
        except ValueError:
            return default

    def _time_limit_seconds(self):
        try:
            value = int(self.time_combo.currentText().strip())
        except ValueError:
            return 70
        return max(5, min(3600, value))
