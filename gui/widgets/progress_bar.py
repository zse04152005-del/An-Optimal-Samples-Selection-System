from PyQt5.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel
from PyQt5.QtCore import Qt, QTimer, QElapsedTimer
from gui.styles import C_ACCENT, C_ACCENT_LIGHT, C_HINT, FONT_MONO

C_GLOW = "#7B8FF7"
C_PB_BG = "#e2e5ef"


class EnhancedProgressBar(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._total_budget_ms = 0
        self._round_cur = 0
        self._round_total = 0
        self._best_size = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)

        container = QWidget()
        container.setFixedHeight(24)
        container.setStyleSheet("background:transparent;")
        layout.addWidget(container)

        self._bar = QProgressBar(container)
        self._bar.setTextVisible(False)
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setStyleSheet(self._static_style())

        self._shadow_label = QLabel(container)
        self._shadow_label.setAlignment(Qt.AlignCenter)
        self._shadow_label.setStyleSheet(
            f"background:transparent; color:rgba(0,0,0,0.35);"
            f"font-family:{FONT_MONO}; font-size:10px; font-weight:600;")

        self._text_label = QLabel(container)
        self._text_label.setAlignment(Qt.AlignCenter)
        self._text_label.setStyleSheet(
            f"background:transparent; color:white;"
            f"font-family:{FONT_MONO}; font-size:10px; font-weight:600;")

        self._elapsed_timer = QElapsedTimer()

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(50)
        self._tick_timer.timeout.connect(self._tick)

        self._glow_timer = QTimer(self)
        self._glow_timer.setInterval(100)
        self._glow_timer.timeout.connect(self._animate_glow)

        self.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        container = self._bar.parent()
        w, h = container.width(), container.height()
        self._bar.setGeometry(0, 0, w, h)
        self._shadow_label.setGeometry(1, 1, w, h)
        self._text_label.setGeometry(0, 0, w, h)

    def start(self, total_budget_ms):
        self.stop()
        self._total_budget_ms = total_budget_ms
        self._round_cur = 0
        self._round_total = 0
        self._best_size = -1
        self._phase = 0.0
        self._bar.setValue(0)
        self._update_text(0, 0.0)
        self._elapsed_timer.start()
        self._tick_timer.start()
        self._glow_timer.start()
        self.setVisible(True)

    def stop(self):
        self._tick_timer.stop()
        self._glow_timer.stop()
        self._total_budget_ms = 0
        self._bar.setStyleSheet(self._static_style())
        self.setVisible(False)

    def set_value(self, value):
        self._bar.setValue(value)

    def set_round_info(self, current, total, best_size):
        self._round_cur = current
        self._round_total = total
        self._best_size = best_size

    def _tick(self):
        if not self.isVisible():
            self.stop()
            return
        if self._total_budget_ms <= 0:
            return
        elapsed_ms = self._elapsed_timer.elapsed()
        value = min(999, int(elapsed_ms * 1000 / self._total_budget_ms))
        self._bar.setValue(value)
        self._update_text(value / 10.0, elapsed_ms / 1000.0)

    def _update_text(self, pct, elapsed_s):
        if self._round_total > 1:
            best = f"  Best:{self._best_size}" if self._best_size >= 0 else ""
            text = f"R{self._round_cur}/{self._round_total}  {pct:.0f}%  {elapsed_s:.1f}s{best}"
        else:
            text = f"Solving  {pct:.0f}%  {elapsed_s:.1f}s"
        self._text_label.setText(text)
        self._shadow_label.setText(text)

    def _animate_glow(self):
        self._phase = (self._phase + 0.015) % 1.0
        p = self._phase
        lo = max(0.0, p - 0.15)
        hi = min(1.0, p + 0.15)
        self._bar.setStyleSheet(f"""
            QProgressBar {{
                border: none; border-radius: 12px;
                background: {C_PB_BG}; height: 24px;
            }}
            QProgressBar::chunk {{
                border-radius: 12px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {C_ACCENT},
                    stop:{lo:.3f} {C_ACCENT},
                    stop:{p:.3f} {C_GLOW},
                    stop:{hi:.3f} {C_ACCENT},
                    stop:1.0 {C_ACCENT}
                );
            }}
        """)

    @staticmethod
    def _static_style():
        return f"""
            QProgressBar {{
                border: none; border-radius: 12px;
                background: {C_PB_BG}; height: 24px;
            }}
            QProgressBar::chunk {{
                border-radius: 12px;
                background: {C_ACCENT};
            }}
        """
