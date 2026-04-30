from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QPushButton, QScrollArea,
    QVBoxLayout, QHBoxLayout, QLabel, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from gui.styles import C_ACCENT, C_BORDER, C_LABEL, FONT_MONO


class SamplePoolGrid(QWidget):

    selection_changed = pyqtSignal(set)

    def __init__(self, columns=10, parent=None):
        super().__init__(parent)
        self._columns = columns
        self._buttons: dict[int, QPushButton] = {}
        self._selected: set[int] = set()
        self._manual_mode = False
        self._target_n = 9

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        hdr = QHBoxLayout()
        lbl = QLabel("SAMPLE POOL")
        lbl.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:10px; letter-spacing:0.5px;")
        self._count_label = QLabel("")
        self._count_label.setStyleSheet(
            f"background:transparent; color:{C_ACCENT}; font-size:11px; font-weight:bold;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        hdr.addWidget(self._count_label)
        outer.addLayout(hdr)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(220)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent; border:none;")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(4)
        self._grid.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._grid_widget)
        outer.addWidget(scroll)

    def rebuild(self, m):
        to_remove = [num for num in list(self._buttons) if num > m]
        for num in to_remove:
            btn = self._buttons.pop(num)
            self._grid.removeWidget(btn)
            btn.deleteLater()
        self._selected.difference_update(to_remove)

        for num in range(1, m + 1):
            if num not in self._buttons:
                btn = QPushButton(str(num))
                btn.setFixedSize(40, 36)
                btn.setCheckable(True)
                btn.clicked.connect(lambda _, n=num: self._toggle(n))
                self._buttons[num] = btn
                row, col = divmod(num - 1, self._columns)
                self._grid.addWidget(btn, row, col)

        self._refresh_display()

    def set_selection(self, selected):
        self._selected = set(selected)
        self._refresh_display()

    def get_selection(self):
        return set(self._selected)

    def set_manual_mode(self, enabled):
        self._manual_mode = enabled

    def set_target_count(self, n):
        self._target_n = n
        self._refresh_display()

    def _toggle(self, num):
        if not self._manual_mode:
            return
        if num in self._selected:
            self._selected.discard(num)
        else:
            if len(self._selected) >= self._target_n:
                QMessageBox.information(
                    self, "Limit reached",
                    f"You can only select {self._target_n} samples (n = {self._target_n}).")
                return
            self._selected.add(num)
        self._refresh_display()
        self.selection_changed.emit(self._selected)

    def _refresh_display(self):
        count = len(self._selected)
        self._count_label.setText(f"{count} / {self._target_n}")

        for num, btn in self._buttons.items():
            active = num in self._selected
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(
                    f"QPushButton{{border-radius:8px;font-family:{FONT_MONO};"
                    f"font-size:12px;font-weight:600;"
                    f"border:none;background:{C_ACCENT};color:white;padding:0px;}}"
                    f"QPushButton:hover{{background:#3d5ce5;}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{border-radius:8px;font-family:{FONT_MONO};"
                    f"font-size:12px;font-weight:600;"
                    f"border:1px solid {C_BORDER};background:#fff;color:#c5cad6;padding:0px;}}"
                    f"QPushButton:hover{{border-color:#c5cad6;color:#1a1f36;}}")
