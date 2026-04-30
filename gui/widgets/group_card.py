from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from gui.styles import (
    C_CARD, C_BORDER, C_LABEL, C_ACCENT,
    C_CHIP_BG, C_CHIP_BORDER, C_CHIP_TEXT, FONT_MONO,
)


def make_group_card(idx, group):
    card = QWidget()
    card.setStyleSheet(
        f"background:{C_CARD}; border:1px solid {C_BORDER}; border-radius:10px;")
    cv = QVBoxLayout(card)
    cv.setContentsMargins(10, 8, 10, 8)
    cv.setSpacing(6)

    num_lbl = QLabel(f"#{idx:02d}")
    num_lbl.setStyleSheet(
        f"background:transparent; color:{C_LABEL}; font-family:{FONT_MONO};"
        f"font-size:11px; font-weight:700;")
    cv.addWidget(num_lbl)

    chips_row = QHBoxLayout()
    chips_row.setSpacing(4)
    for num in group:
        chip = QLabel(str(num))
        chip.setFixedSize(30, 26)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background:{C_CHIP_BG}; border:1px solid {C_CHIP_BORDER};"
            f"color:{C_CHIP_TEXT}; font-family:{FONT_MONO};"
            f"font-size:12px; font-weight:700; border-radius:6px;")
        chips_row.addWidget(chip)
    chips_row.addStretch()
    cv.addLayout(chips_row)
    return card
