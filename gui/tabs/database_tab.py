import math

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QScrollArea, QGridLayout, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize

from gui.styles import (
    C_ACCENT, C_ACCENT_LIGHT, C_ACCENT_BORDER,
    C_BG, C_CARD, C_BORDER, C_BORDER_HOV, C_TEXT, C_LABEL, C_HINT,
    C_PARAM_BG,
    C_CHIP_BG, C_CHIP_BORDER, C_CHIP_TEXT,
    C_OPTIMAL_BG, C_OPTIMAL_BORDER, C_OPTIMAL_TEXT,
    C_FEASIBLE_BG, C_FEASIBLE_BORDER, C_FEASIBLE_TEXT,
    FONT_MONO, FONT_SANS,
    SS_ACCENT_SM, SS_DANGER_SM, SS_SECTION_TITLE,
)


class DatabaseTab(QWidget):

    load_requested = pyqtSignal(dict)
    export_requested = pyqtSignal(str)

    DB_GROUPS_PER_PAGE = 18

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._grp_page = 0
        self._grp_all: list = []
        self.setStyleSheet(f"background:{C_BG};")
        self._init_layout()
        self.refresh_list()

    def _init_layout(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ──── LEFT: file list ────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(320)
        left.setStyleSheet(
            f"background:{C_CARD}; border-right:1px solid {C_BORDER};")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 16, 16, 16)
        lv.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(self._section_title("SAVED RESULTS"))
        hdr.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C_LABEL};border:none;"
            f"font-size:11px;font-weight:500;}}"
            f"QPushButton:hover{{color:{C_TEXT};}}")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_list)
        hdr.addWidget(refresh_btn)
        lv.addLayout(hdr)

        self.db_list = QListWidget()
        self.db_list.setStyleSheet(f"""
            QListWidget {{
                background: transparent; border: none; outline: none;
            }}
            QListWidget::item {{
                background: transparent; border: none;
                padding: 8px 10px; border-radius: 8px;
                margin-bottom: 2px;
            }}
            QListWidget::item:selected {{
                background: {C_ACCENT_LIGHT};
                border-left: 3px solid {C_ACCENT};
            }}
            QListWidget::item:hover:!selected {{
                background: {C_PARAM_BG};
            }}
        """)
        self.db_list.currentRowChanged.connect(self._on_row_changed)
        lv.addWidget(self.db_list, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.display_btn = QPushButton("Display")
        self.display_btn.setStyleSheet(SS_ACCENT_SM)
        self.display_btn.setCursor(Qt.PointingHandCursor)
        self.display_btn.clicked.connect(self._display_selected)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet(SS_DANGER_SM)
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.display_btn, stretch=1)
        btn_row.addWidget(self.delete_btn, stretch=1)
        lv.addLayout(btn_row)

        path_lbl = QLabel(f"Folder: {self.db_manager.get_db_folder()}")
        path_lbl.setStyleSheet(f"color:{C_HINT}; font-size:9px;")
        path_lbl.setWordWrap(True)
        lv.addWidget(path_lbl)

        outer.addWidget(left)

        # ──── RIGHT: detail panel ────────────────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background:{C_BG};")
        rv = QVBoxLayout(right)
        rv.setContentsMargins(20, 16, 20, 16)
        rv.setSpacing(12)

        # Detail header
        det_hdr = QHBoxLayout()
        self._detail_title = QLabel("")
        self._detail_title.setWordWrap(True)
        self._detail_title.setStyleSheet(
            f"color:{C_TEXT}; font-weight:600; font-size:14px;")
        det_hdr.addWidget(self._detail_title, stretch=1)

        self._load_btn = QPushButton("Load into Computation")
        self._load_btn.setStyleSheet(SS_ACCENT_SM)
        self._load_btn.setCursor(Qt.PointingHandCursor)
        self._load_btn.clicked.connect(self._on_load_click)
        self._export_btn = QPushButton("Export")
        self._export_btn.setStyleSheet(
            f"QPushButton{{background:{C_CARD};color:#64748b;"
            f"border:1px solid {C_BORDER};border-radius:8px;"
            f"font-size:12px;padding:6px 14px;}}"
            f"QPushButton:hover{{border-color:{C_BORDER_HOV};}}")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.clicked.connect(self._on_export_click)
        det_hdr.addWidget(self._load_btn)
        det_hdr.addWidget(self._export_btn)
        rv.addLayout(det_hdr)

        # Status + stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._det_groups = self._mini_stat("--", "groups")
        self._det_time = self._mini_stat("--", "solve time")
        self._det_status_badge = QWidget()
        stats_row.addWidget(self._det_groups)
        stats_row.addWidget(self._det_time)
        stats_row.addWidget(self._det_status_badge)
        stats_row.addStretch()
        rv.addLayout(stats_row)

        # Pool row
        pool_hdr = QLabel("")
        pool_hdr.setStyleSheet(SS_SECTION_TITLE)
        pool_hdr.setObjectName("poolHdr")
        rv.addWidget(pool_hdr)
        self._pool_hdr = pool_hdr

        pool_scroll_w = QWidget()
        pool_scroll_w.setStyleSheet("background:transparent;")
        self._pool_chip_ly = QHBoxLayout(pool_scroll_w)
        self._pool_chip_ly.setContentsMargins(0, 0, 0, 0)
        self._pool_chip_ly.setSpacing(4)
        self._pool_chip_ly.addStretch()
        rv.addWidget(pool_scroll_w)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C_BORDER}; border:none;")
        rv.addWidget(sep)

        rv.addWidget(self._section_title("RESULT GROUPS"))

        # Groups scroll
        grp_scroll = QScrollArea()
        grp_scroll.setWidgetResizable(True)
        grp_scroll.setStyleSheet("background:transparent; border:none;")
        self._grp_container = QWidget()
        self._grp_container.setStyleSheet("background:transparent;")
        self._grp_layout = QGridLayout(self._grp_container)
        self._grp_layout.setSpacing(8)
        self._grp_layout.setContentsMargins(0, 0, 0, 0)
        self._grp_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        grp_scroll.setWidget(self._grp_container)
        rv.addWidget(grp_scroll, stretch=1)

        # Group pagination
        self._grp_pager = QWidget()
        self._grp_pager.setVisible(False)
        gp_ly = QHBoxLayout(self._grp_pager)
        gp_ly.setContentsMargins(0, 4, 0, 0)
        gp_ly.setSpacing(6)
        self._grp_prev = QPushButton("<")
        self._grp_prev.setFixedSize(28, 28)
        self._grp_prev.setStyleSheet(
            f"QPushButton{{background:{C_CARD};border:1px solid {C_BORDER};"
            f"border-radius:6px;font-size:12px;color:{C_TEXT};}}"
            f"QPushButton:hover{{background:#f0f2f5;}}")
        self._grp_prev.clicked.connect(lambda: self._change_grp_page(-1))
        self._grp_next = QPushButton(">")
        self._grp_next.setFixedSize(28, 28)
        self._grp_next.setStyleSheet(self._grp_prev.styleSheet())
        self._grp_next.clicked.connect(lambda: self._change_grp_page(1))
        self._grp_dots = QWidget()
        self._grp_dots_ly = QHBoxLayout(self._grp_dots)
        self._grp_dots_ly.setContentsMargins(0, 0, 0, 0)
        self._grp_dots_ly.setSpacing(4)
        self._grp_page_info = QLabel("")
        self._grp_page_info.setStyleSheet(f"color:{C_HINT}; font-size:11px;")
        gp_ly.addWidget(self._grp_prev)
        gp_ly.addWidget(self._grp_dots)
        gp_ly.addWidget(self._grp_next)
        gp_ly.addStretch()
        gp_ly.addWidget(self._grp_page_info)
        rv.addWidget(self._grp_pager)

        self._detail_panel = right
        self._detail_panel.setVisible(False)
        outer.addWidget(right, stretch=1)

        # Placeholder
        self._placeholder = QLabel(
            "Select a record from the list\nand press Display.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(f"color:{C_HINT}; font-size:13px;")
        outer.addWidget(self._placeholder, stretch=1)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _section_title(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(SS_SECTION_TITLE)
        return lbl

    def _mini_stat(self, value, label):
        w = QWidget()
        w.setStyleSheet(f"background:{C_PARAM_BG}; border-radius:10px;")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(12, 8, 12, 8)
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

    def _result_card(self, idx, group):
        card = QWidget()
        card.setStyleSheet(
            f"QWidget{{background:{C_CARD};border:1px solid {C_BORDER};border-radius:10px;}}"
            f"QWidget:hover{{border-color:{C_BORDER_HOV};}}")
        ly = QVBoxLayout(card)
        ly.setContentsMargins(10, 8, 10, 8)
        ly.setSpacing(6)
        num = QLabel(f"#{idx:02d}")
        num.setStyleSheet(
            f"background:transparent;color:{C_LABEL};font-family:{FONT_MONO};"
            f"font-size:11px;font-weight:700;")
        ly.addWidget(num)
        chips = QHBoxLayout()
        chips.setSpacing(4)
        for v in group:
            chip = QLabel(str(v))
            chip.setFixedSize(30, 26)
            chip.setAlignment(Qt.AlignCenter)
            chip.setStyleSheet(
                f"background:{C_CHIP_BG};border:1px solid {C_CHIP_BORDER};"
                f"color:{C_CHIP_TEXT};font-family:{FONT_MONO};"
                f"font-size:12px;font-weight:700;border-radius:6px;")
            chips.addWidget(chip)
        chips.addStretch()
        ly.addLayout(chips)
        return card

    def _set_status_badge(self, status):
        old = self._det_status_badge
        parent_ly = old.parentWidget().layout() if old.parentWidget() else None

        badge = QWidget()
        badge.setObjectName("statusBadge")
        ly = QHBoxLayout(badge)
        ly.setContentsMargins(10, 6, 10, 6)
        ly.setSpacing(6)

        if status == "OPTIMAL":
            bg, border, text = C_OPTIMAL_BG, C_OPTIMAL_BORDER, C_OPTIMAL_TEXT
        elif "FEASIBLE" in status:
            bg, border, text = C_FEASIBLE_BG, C_FEASIBLE_BORDER, C_FEASIBLE_TEXT
        else:
            bg, border, text = C_PARAM_BG, C_BORDER, C_LABEL

        badge.setStyleSheet(
            f"background:{bg};border:1.5px solid {border};border-radius:12px;")
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background:{text};border-radius:4px;")
        lbl = QLabel(status[:12])
        lbl.setStyleSheet(
            f"background:transparent;color:{text};font-size:12px;font-weight:600;")
        ly.addWidget(dot)
        ly.addWidget(lbl)

        if parent_ly:
            idx = parent_ly.indexOf(old)
            parent_ly.removeWidget(old)
            old.deleteLater()
            parent_ly.insertWidget(idx, badge)
        self._det_status_badge = badge

    # ── Public API ───────────────────────────────────────────────────────────

    def refresh_list(self):
        self.db_list.clear()
        results = self.db_manager.list_results()
        for r in results:
            fn = r['filename']
            display = fn.replace('.db', '')
            parts = display.split('-')
            if len(parts) >= 7:
                params = f"m={parts[0]} n={parts[1]} k={parts[2]} j={parts[3]} s={parts[4]} | {parts[6]} groups"
            else:
                params = ""

            item_widget = QWidget()
            item_widget.setStyleSheet("background:transparent;")
            ly = QVBoxLayout(item_widget)
            ly.setContentsMargins(0, 0, 0, 0)
            ly.setSpacing(1)
            name_lbl = QLabel(display)
            name_lbl.setStyleSheet(
                f"background:transparent;color:{C_TEXT};font-family:{FONT_MONO};"
                f"font-size:12px;font-weight:600;")
            param_lbl = QLabel(params)
            param_lbl.setStyleSheet(
                f"background:transparent;color:{C_LABEL};font-size:11px;")
            ly.addWidget(name_lbl)
            ly.addWidget(param_lbl)

            item = QListWidgetItem()
            item.setData(Qt.UserRole, fn)
            item.setSizeHint(QSize(0, 48))
            self.db_list.addItem(item)
            self.db_list.setItemWidget(item, item_widget)

    def get_selected_filename(self):
        item = self.db_list.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    # ── Internal handlers ────────────────────────────────────────────────────

    def _on_row_changed(self, row):
        if row >= 0:
            self._display_selected()

    def _display_selected(self):
        filename = self.get_selected_filename()
        if not filename:
            QMessageBox.warning(self, "Error", "Please select a record.")
            return
        result = self.db_manager.load_result(filename)
        if not result:
            QMessageBox.critical(self, "Error", "Failed to load record.")
            return

        display_name = filename.replace('.db', '')
        self._detail_title.setText(
            f"{display_name}\n"
            f"m={result['m']}  n={result['n']}  k={result['k']}  "
            f"j={result['j']}  s={result['s']}")

        self._det_groups.findChild(QLabel, "miniVal").setText(str(result['num_groups']))
        t = result['solve_time']
        self._det_time.findChild(QLabel, "miniVal").setText(
            f"{t * 1000:.0f}ms" if t < 1 else f"{t:.1f}s")
        self._set_status_badge(result.get('status', 'UNKNOWN'))

        # Pool chips
        while self._pool_chip_ly.count() > 1:
            item = self._pool_chip_ly.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        n_samples = len(result['samples'])
        self._pool_hdr.setText(f"POOL -- {n_samples} samples drawn for this run")
        for num in result['samples']:
            chip = QLabel(str(num))
            chip.setFixedSize(30, 24)
            chip.setAlignment(Qt.AlignCenter)
            chip.setStyleSheet(
                f"background:#f1f5f9;border:1px solid #e2e8f0;color:#475569;"
                f"font-family:{FONT_MONO};font-size:11px;font-weight:600;border-radius:6px;")
            self._pool_chip_ly.insertWidget(self._pool_chip_ly.count() - 1, chip)

        # Group cards (paginated)
        self._grp_all = result['groups']
        self._grp_page = 0
        self._render_grp_page()
        self._grp_pager.setVisible(len(self._grp_all) > self.DB_GROUPS_PER_PAGE)

        self._placeholder.setVisible(False)
        self._detail_panel.setVisible(True)

    def _render_grp_page(self):
        while self._grp_layout.count():
            item = self._grp_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(self._grp_all)
        if total == 0:
            return

        pp = self.DB_GROUPS_PER_PAGE
        start = self._grp_page * pp
        end = min(start + pp, total)
        page_items = self._grp_all[start:end]

        COLS = 3
        for i, group in enumerate(page_items):
            card = self._result_card(start + i + 1, group)
            self._grp_layout.addWidget(card, i // COLS, i % COLS)

        total_pages = math.ceil(total / pp)
        self._grp_prev.setEnabled(self._grp_page > 0)
        self._grp_next.setEnabled(self._grp_page < total_pages - 1)
        self._grp_page_info.setText(f"{start + 1}-{end} of {total}")
        self._render_grp_dots(total_pages)

    def _render_grp_dots(self, total_pages):
        while self._grp_dots_ly.count():
            item = self._grp_dots_ly.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i in range(min(total_pages, 12)):
            dot = QWidget()
            if i == self._grp_page:
                dot.setFixedSize(20, 8)
                dot.setStyleSheet(
                    f"background:{C_ACCENT}; border-radius:4px;")
            else:
                dot.setFixedSize(8, 8)
                dot.setStyleSheet(
                    f"background:#dfe2e8; border-radius:4px;")
            self._grp_dots_ly.addWidget(dot)

    def _change_grp_page(self, delta):
        total_pages = math.ceil(len(self._grp_all) / self.DB_GROUPS_PER_PAGE)
        new_page = self._grp_page + delta
        if 0 <= new_page < total_pages:
            self._grp_page = new_page
            self._render_grp_page()

    def _delete_selected(self):
        filename = self.get_selected_filename()
        if not filename:
            QMessageBox.warning(self, "Error", "Please select a result to delete.")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete {filename}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.db_manager.delete_result(filename):
                self.refresh_list()
                self._detail_panel.setVisible(False)
                self._placeholder.setVisible(True)
            else:
                QMessageBox.critical(self, "Error", "Failed to delete file.")

    def _on_load_click(self):
        filename = self.get_selected_filename()
        if not filename:
            QMessageBox.warning(self, "Error", "Please select a result to load.")
            return
        result = self.db_manager.load_result(filename)
        if result:
            self.load_requested.emit(result)

    def _on_export_click(self):
        filename = self.get_selected_filename()
        if filename:
            self.export_requested.emit(filename)
