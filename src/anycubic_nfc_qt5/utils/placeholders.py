# src/anycubic_nfc_qt5/utils/placeholders.py
from PyQt5 import QtWidgets, QtCore

def set_placeholder(combo: QtWidgets.QComboBox, text: str):
    """Insert a disabled, non-selectable first item as placeholder."""
    combo.clear()
    combo.addItem(text)
    m = combo.model()
    idx = m.index(0, 0)
    # disable first item (placeholder)
    m.setData(idx, 0, QtCore.Qt.UserRole - 1)
    it = getattr(m, "item", None)
    if callable(it):
        item0 = m.item(0)
        if item0:
            item0.setEnabled(False)
            item0.setSelectable(False)
    combo.setCurrentIndex(0)