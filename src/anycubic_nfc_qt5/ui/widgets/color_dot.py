# src/anycubic_nfc_qt5/ui/widgets/color_dot.py
from PyQt5 import QtWidgets, QtGui, QtCore
from ...utils.colors import normalize_hex

class ColorDot(QtWidgets.QWidget):
    """Simple circular color indicator next to the color combo."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QtGui.QColor("#000000")
        self.setFixedSize(22, 22)

    def set_color_hex(self, hex_str: str):
        """Set color from '#RRGGBB' string."""
        self._color = QtGui.QColor(normalize_hex(hex_str))
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = self.rect().adjusted(2, 2, -2, -2)
        p.setPen(QtGui.QPen(QtGui.QColor("#444"), 1))
        p.setBrush(QtGui.QBrush(self._color))
        p.drawEllipse(r)
        p.end()