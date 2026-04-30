from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from gui.styles import C_CARD, C_BORDER, C_LABEL, C_TEXT, C_ACCENT


class StatCard(QWidget):

    def __init__(self, label_text, value_text="--", accent_color=C_ACCENT, parent=None):
        super().__init__(parent)
        self._accent = accent_color
        self.setObjectName("statCard")
        self._update_card_style()
        ly = QVBoxLayout(self)
        ly.setContentsMargins(12, 10, 12, 10)
        ly.setSpacing(2)

        self._label = QLabel(label_text.upper())
        self._label.setStyleSheet(
            f"background:transparent; color:{C_LABEL}; font-size:10px; letter-spacing:0.5px;")

        self._value = QLabel(value_text)
        self._value.setStyleSheet(
            f"background:transparent; color:{C_TEXT}; font-size:20px; font-weight:bold;")

        ly.addWidget(self._label)
        ly.addWidget(self._value)

    def _update_card_style(self):
        self.setStyleSheet(f"""
            QWidget#statCard {{
                background: {C_CARD};
                border: 1px solid {C_BORDER};
                border-left: 4px solid {self._accent};
                border-radius: 8px;
                min-width: 90px;
            }}
        """)

    def set_value(self, text):
        self._value.setText(text)

    def set_accent(self, color):
        self._accent = color
        self._update_card_style()

    def value(self):
        return self._value.text()

    def flash(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(0.3)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: self.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeleteWhenStopped)
