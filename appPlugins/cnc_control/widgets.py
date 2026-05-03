import math

from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtCore import Qt


class FluidStyleButton(QtWidgets.QToolButton):
    def __init__(self, text="", color="#31b0d5", hover="#269abc", text_color="white", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QtCore.QSize(18, 18))
        self.setMinimumHeight(28)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Fixed)


class DashboardGauge(QtWidgets.QWidget):
    def __init__(self, title, unit, max_value, accent="#31b0d5", parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.max_value = float(max_value)
        self.accent = QtGui.QColor(accent)
        self._value = 0.0
        self._target = 0.0
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._animate_value)
        self.setMinimumSize(150, 170)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

    def set_value(self, value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0.0
        self._target = max(0.0, value)
        if not self._timer.isActive():
            self._timer.start()

    def _animate_value(self):
        delta = self._target - self._value
        if abs(delta) < 0.5:
            self._value = self._target
            self._timer.stop()
        else:
            self._value += delta * 0.18
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        palette = self.palette()
        text_color = palette.color(QtGui.QPalette.ColorRole.WindowText)
        mid_color = palette.color(QtGui.QPalette.ColorRole.Mid)
        base_color = palette.color(QtGui.QPalette.ColorRole.Base)

        rect = self.rect().adjusted(6, 4, -6, -4)
        painter.setPen(QtGui.QPen(mid_color, 1))
        painter.setBrush(base_color)
        painter.drawRoundedRect(QtCore.QRectF(rect), 6, 6)

        title_font = QtGui.QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSize(max(8, title_font.pointSize()))
        painter.setFont(title_font)
        painter.setPen(text_color)
        painter.drawText(rect.adjusted(0, 4, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.title)

        gauge_top = rect.top() + 24
        gauge_bottom = rect.bottom() - 30
        gauge_height = max(40, gauge_bottom - gauge_top)
        side = min(rect.width() - 26, gauge_height)
        arc_rect = QtCore.QRectF(
            rect.center().x() - side / 2,
            gauge_top + (gauge_height - side) / 2,
            side,
            side
        )

        track_pen = QtGui.QPen(mid_color.lighter(135), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(arc_rect, 225 * 16, -270 * 16)

        segment_span = -90 * 16
        for start, color in [
            (225, "#4cc26f"),
            (135, "#f0c04a"),
            (45, "#e85d5d"),
        ]:
            painter.setPen(QtGui.QPen(QtGui.QColor(color), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(arc_rect, start * 16, segment_span)

        ratio = 0.0 if self.max_value <= 0 else self._value / self.max_value
        ratio = max(0.0, min(ratio, 1.0))
        painter.setPen(QtGui.QPen(self.accent, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc_rect.adjusted(7, 7, -7, -7), 225 * 16, int(-270 * ratio * 16))

        center = QtCore.QPointF(arc_rect.center().x(), arc_rect.center().y() + side * 0.12)
        needle_radius = side * 0.36
        angle = 225 - (270 * ratio)
        rad = angle * 3.141592653589793 / 180.0
        needle_end = QtCore.QPointF(
            center.x() + needle_radius * math.cos(rad),
            center.y() - needle_radius * math.sin(rad)
        )
        painter.setPen(QtGui.QPen(text_color, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(center, needle_end)
        painter.setBrush(self.accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 4, 4)

        value_font = QtGui.QFont(painter.font())
        value_font.setBold(True)
        value_font.setPointSize(11)
        painter.setFont(value_font)
        painter.setPen(text_color)
        value_text = "%d %s" % (round(self._value), self.unit)
        painter.drawText(rect.adjusted(0, 0, 0, -8), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, value_text)
