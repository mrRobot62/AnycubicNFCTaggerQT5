# src/anycubic_nfc_qt5/nfc/presence.py
from PyQt5 import QtCore
from smartcard.CardMonitoring import CardMonitor, CardObserver

class QtPresenceBridge(QtCore.QObject):
    """Qt bridge to emit signals from CardObserver callbacks (background thread)."""
    presenceChanged = QtCore.pyqtSignal(bool)  # True = card present, False = removed

class CardPresenceObserver(CardObserver):
    """pyscard CardObserver that forwards insert/remove events to Qt via a bridge."""
    def __init__(self, bridge: QtPresenceBridge):
        super().__init__()
        self._bridge = bridge

    def update(self, observable, actions):
        """Called by pyscard on card inserted/removed."""
        (added, removed) = actions
        if added and len(added) > 0:
            self._bridge.presenceChanged.emit(True)
        if removed and len(removed) > 0:
            self._bridge.presenceChanged.emit(False)

def start_presence_monitor(bridge: QtPresenceBridge):
    """Create and start a CardMonitor with observer; returns (monitor, observer)."""
    monitor = CardMonitor()
    observer = CardPresenceObserver(bridge)
    monitor.addObserver(observer)
    return monitor, observer