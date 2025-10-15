# src/anycubic_nfc_qt5/app.py
import sys
from PyQt5 import QtWidgets, QtGui, QtCore
from .config.filaments import load_filaments
from importlib import resources
from anycubic_nfc_qt5.nfc.pcsc import list_readers, connect_first_reader, read_atr, read_uid


PLACEHOLDER_FILAMENT = "select filament"
PLACEHOLDER_COLOR = "select color"

def set_placeholder(combo: QtWidgets.QComboBox, text: str):
    """Insert a disabled, non-selectable first item as placeholder."""
    combo.clear()
    combo.addItem(text)
    # disable/select-block the placeholder row
    m = combo.model()
    idx = m.index(0, 0)
    m.setData(idx, 0, QtCore.Qt.UserRole - 1)  # disable
    # QComboBox uses QStandardItemModel by default, so this is safe:
    it = getattr(m, "item", None)
    if callable(it):
        item0 = m.item(0)
        if item0:
            item0.setEnabled(False)
            item0.setSelectable(False)
    combo.setCurrentIndex(0)

def normalize_hex(hex_str: str) -> str:
    """Convert '#RRGGBBAA' -> '#RRGGBB'. Keep '#RRGGBB' unchanged."""
    s = (hex_str or "").strip()
    if not s.startswith("#"):
        return "#000000"
    if len(s) >= 9:  # '#RRGGBBAA' -> take first 7 chars
        return s[:7]
    if len(s) == 7:
        return s
    # Fallback if malformed
    return "#000000"

class ColorDot(QtWidgets.QWidget):
    """Simple circular color indicator next to the color combo."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QtGui.QColor("#000000")
        self.setFixedSize(22, 22)  # small round indicator

    def set_color_hex(self, hex_str: str):
        """Set color from '#RRGGBB' string."""
        self._color = QtGui.QColor(normalize_hex(hex_str))
        self.update()

    def paintEvent(self, event):
        # Draw a filled circle with a thin border
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = self.rect().adjusted(2, 2, -2, -2)
        p.setPen(QtGui.QPen(QtGui.QColor("#444"), 1))
        p.setBrush(QtGui.QBrush(self._color))
        p.drawEllipse(r)
        p.end()

class NFCWorker(QtCore.QThread):
    """Background worker that polls the first PC/SC reader and detects card presence."""
    readerStateChanged = QtCore.pyqtSignal(bool)                 # True = connected (card present), False = no card
    cardDetected = QtCore.pyqtSignal(bytes, object)              # atr: bytes, uid: Optional[bytes]

    def __init__(self, parent=None, poll_interval_ms: int = 700):
        super().__init__(parent)
        self._running = True
        self._poll_interval_ms = poll_interval_ms

    def stop(self):
        """Stop the thread loop gracefully."""
        self._running = False

    def run(self):
        """Poll for card presence; emit signals on state change and when a card is detected."""
        was_connected = False
        while self._running:
            try:
                # No reader available?
                if not list_readers():
                    if was_connected:
                        self.readerStateChanged.emit(False)
                        was_connected = False
                    self.msleep(self._poll_interval_ms)
                    continue

                # Try to connect to first reader; success means a card is present
                conn = connect_first_reader()
                if conn is None:
                    if was_connected:
                        self.readerStateChanged.emit(False)
                        was_connected = False
                    self.msleep(self._poll_interval_ms)
                    continue

                try:
                    conn.connect()
                    # Card present
                    if not was_connected:
                        self.readerStateChanged.emit(True)
                        was_connected = True

                    atr = read_atr(conn) or b""
                    uid, sw1, sw2 = read_uid(conn)  # may be (None, sw1, sw2)
                    self.cardDetected.emit(atr, uid)

                except Exception:
                    # No card / connect failed
                    if was_connected:
                        self.readerStateChanged.emit(False)
                        was_connected = False

                finally:
                    try:
                        conn.disconnect()
                    except Exception:
                        pass

            except Exception:
                # Any unexpected error → wait and continue
                pass

            self.msleep(self._poll_interval_ms)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnycubicNFCTaggerQT5")
        self.resize(620, 400)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # === NFC Icon ===
        self.icon_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.icon_label.setMinimumHeight(120)
        layout.addWidget(self.icon_label)

        # Load icons from packaged resources
        self.icons = {}
        for state, fname in {
            "red": "nfc_red.png",
            "green": "nfc_green.png",
        }.items():
            try:
                data = resources.files("anycubic_nfc_qt5.ui.resources").joinpath(fname).read_bytes()
                pm = QtGui.QPixmap()
                pm.loadFromData(data)
                self.icons[state] = pm
            except Exception as e:
                print(f"[WARN] Could not load {fname}: {e}")
        self.set_reader_connected(False)  # start state

        # === Selection row ===
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)

        left_box = QtWidgets.QGroupBox("Choose filament")
        right_box = QtWidgets.QGroupBox("Choose color")
        row.addWidget(left_box, 1)
        row.addWidget(right_box, 1)

        # Left side: filament combo
        self.combo_filament = QtWidgets.QComboBox()
        v_left = QtWidgets.QVBoxLayout(left_box)
        v_left.addWidget(self.combo_filament)

        # Right side: color combo + color dot + hex label
        self.combo_color = QtWidgets.QComboBox()
        self.color_dot = ColorDot()
        self.color_hex_label = QtWidgets.QLabel("")  # shows '#RRGGBB'

        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self.combo_color, 1)
        right_row.addWidget(self.color_dot, 0, QtCore.Qt.AlignVCenter)
        right_row.addWidget(self.color_hex_label, 0, QtCore.Qt.AlignVCenter)

        v_right = QtWidgets.QVBoxLayout(right_box)
        v_right.addLayout(right_row)

        # === SKU Display (prominent) ===
        self.sku_label = QtWidgets.QLabel("", alignment=QtCore.Qt.AlignCenter)
        self.sku_label.setObjectName("skuLabel")
        # Make it pop: bold + larger font
        self.sku_label.setStyleSheet("#skuLabel { font-weight: 600; font-size: 18px; }")
        self.sku_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.sku_label)

        # === Buttons row ===
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)
        self.btn_read = QtWidgets.QPushButton("READ NFC")
        self.btn_write = QtWidgets.QPushButton("WRITE NFC")
        btn_row.addStretch()
        btn_row.addWidget(self.btn_read)
        btn_row.addWidget(self.btn_write)
        btn_row.addStretch()

        # === Log output ===
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        # placeholders first
        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)
        self._set_color_indicator(None)

        self.statusBar().showMessage("Ready")

        # Load filaments
        try:
            self.by_filament, self.by_sku = load_filaments(None)
            names = sorted(self.by_filament.keys(), key=str.casefold)
            # append items AFTER placeholder
            for name in names:
                self.combo_filament.addItem(name)
            self.log(f"Loaded {sum(len(v) for v in self.by_filament.values())} filament records.")
        except Exception as e:
            self.log(f"[Error] Failed to load filaments: {e}")

        # --- Signals ---
        self.combo_filament.currentTextChanged.connect(self.on_filament_changed)
        self.combo_color.currentTextChanged.connect(self.on_color_changed)
        self.btn_read.clicked.connect(self.on_read)
        self.btn_write.clicked.connect(self.on_write)

        # --- NFC worker (real reader status) ---
        self.reader_connected = False
        self.nfc_worker = NFCWorker(self)
        self.nfc_worker.readerStateChanged.connect(self.on_reader_state_changed)
        self.nfc_worker.cardDetected.connect(self.on_card_detected)
        self.nfc_worker.start()

        self._update_actions()

    # === UI Helpers ===

    def _set_sku(self, sku: str | None):
        """Update prominent SKU label."""
        self.sku_label.setText(f"SKU: {sku}" if sku else "")

    def set_reader_connected(self, state: bool):
        """Show the correct colored NFC icon."""
        pix = self.icons.get("green" if state else "red")
        if not pix or pix.isNull():
            self.icon_label.setText("[missing icon]")
            return
        self.icon_label.setPixmap(pix.scaledToWidth(100, QtCore.Qt.SmoothTransformation))

    def _check_reader_state(self):
        """Simulate: toggle connection status (for now)."""
        self.reader_connected = not self.reader_connected
        self.set_reader_connected(self.reader_connected)
        self.statusBar().showMessage("Reader connected" if self.reader_connected else "Reader disconnected")

    def log(self, msg: str):
        self.output.appendPlainText(msg)

    def _update_actions(self):
        """Enable/disable buttons based on selection state."""
        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        self.btn_write.setEnabled(filament_ok and color_ok)
        self.btn_read.setEnabled(True)

    def _set_color_indicator(self, hex_str: str | None):
        """Update the color dot and hex text (expects '#RRGGBB' or None)."""
        if not hex_str:
            self.color_dot.set_color_hex("#000000")
            self.color_hex_label.setText("")
            return
        rgb = normalize_hex(hex_str)
        self.color_dot.set_color_hex(rgb)
        self.color_hex_label.setText(rgb)

    def on_filament_changed(self, filament_name: str):
        """Handle filament selection change."""
        if self.combo_filament.currentIndex() == 0 or filament_name == PLACEHOLDER_FILAMENT:
            set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
            self.combo_color.setEnabled(False)
            self._set_color_indicator(None)
            self._update_actions()
            return

        records = self.by_filament.get(filament_name, [])
        self.log(f"Selected filament: {filament_name} ({len(records)} variants)")

        # Build unique color list; store SKU + hex in itemData for later use
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(True)
        seen = set()
        for rec in records:
            if rec.color not in seen:
                self.combo_color.addItem(rec.color, (rec.sku, rec.color_hex))
                seen.add(rec.color)

        self._set_color_indicator(None)
        self._set_sku(None)  # <-- reset SKU until a color is chosen
        self._update_actions()

    def on_color_changed(self, color_name: str):
        """Update color dot on color selection."""
        if self.combo_color.currentIndex() == 0 or color_name == PLACEHOLDER_COLOR:
            self._set_color_indicator(None)
            self._set_sku(None)  # <-- reset
            self._update_actions()
            return
        data = self.combo_color.currentData()  # (sku, color_hex)
        if data:
            sku, hex_str = data
            self._set_color_indicator(hex_str)
            # Optional log:
            self._set_sku(sku)  # <-- show selected SKU prominently
            self.log(f"Selected color: {color_name} [{normalize_hex(hex_str)}], SKU={sku}")
        self._update_actions()

    def on_reader_state_changed(self, connected: bool):
        """Switch icon and status bar when reader/card state changes."""
        self.reader_connected = connected
        self.set_reader_connected(connected)
        self.statusBar().showMessage("Reader connected" if connected else "Reader disconnected")

    def on_card_detected(self, atr: bytes, uid):
        """Log ATR and optional UID whenever a card is detected."""
        # Format helper
        def fmt(b: bytes) -> str:
            return " ".join(f"{x:02X}" for x in b) if b else "(empty)"

        if atr:
            self.log(f"[OK] ATR: {fmt(atr)}")
        if uid is not None:
            self.log(f"[OK] UID: {fmt(uid)}")
        else:
            # UID not available is fine on ACR122U if command unsupported (e.g. SW=6300)
            self.log("[INFO] UID not available on this reader/card.")

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Ensure worker is stopped before window closes."""
        try:
            if hasattr(self, "nfc_worker") and self.nfc_worker.isRunning():
                self.nfc_worker.stop()
                self.nfc_worker.wait(1500)
        finally:
            super().closeEvent(event)

    # === Buttons ===
    def on_read(self):
        self.log("[INFO] READ NFC clicked")

    def on_write(self):
        self.log("[INFO] WRITE NFC clicked")


def run_app():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())