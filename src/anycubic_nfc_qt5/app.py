# src/anycubic_nfc_qt5/app.py
import sys
import time
import re
from PyQt5 import QtWidgets, QtGui, QtCore
from importlib import resources
from .config.filaments import load_filaments
from anycubic_nfc_qt5.nfc.pcsc import list_readers, connect_first_reader, read_atr, read_uid
from anycubic_nfc_qt5.nfc.pcsc import read_anycubic_fields, interpret_anycubic

# pyscard presence monitor (no APDU, just insert/remove)
from smartcard.CardMonitoring import CardMonitor, CardObserver

PLACEHOLDER_FILAMENT = "select filament"
PLACEHOLDER_COLOR = "select color"

def sku_base(sku: str) -> str:
    """Return alphanumeric part before '-', e.g. 'AHHSCG-101' -> 'AHHSCG'."""
    if not sku:
        return ""
    # take substring before first '-' and keep only A–Z, a–z, 0–9
    head = sku.split("-", 1)[0]
    return re.sub(r"[^A-Za-z0-9]", "", head)

def set_placeholder(combo: QtWidgets.QComboBox, text: str):
    """Insert a disabled, non-selectable first item as placeholder."""
    combo.clear()
    combo.addItem(text)
    m = combo.model()
    idx = m.index(0, 0)
    m.setData(idx, 0, QtCore.Qt.UserRole - 1)  # disable
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
    if len(s) >= 9:
        return s[:7]
    if len(s) == 7:
        return s
    return "#000000"

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

# ---------- Card presence monitor (no reading) ----------
class _QtPresenceBridge(QtCore.QObject):
    """Qt bridge object to emit signals from CardObserver callbacks (which run in a background thread)."""
    presenceChanged = QtCore.pyqtSignal(bool)  # True = card present, False = removed

class _CardPresenceObserver(CardObserver):
    """pyscard CardObserver that forwards insert/remove events to Qt via a bridge."""
    def __init__(self, bridge: _QtPresenceBridge):
        super().__init__()
        self._bridge = bridge

    def update(self, observable, actions):
        """Called by pyscard on card inserted/removed."""
        (added, removed) = actions
        if added and len(added) > 0:
            self._bridge.presenceChanged.emit(True)
        if removed and len(removed) > 0:
            self._bridge.presenceChanged.emit(False)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnycubicNFCTaggerQT5")
        self.resize(620, 400)

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # === NFC Icon + Refresh ===
        icon_row = QtWidgets.QHBoxLayout()
        layout.addLayout(icon_row)
        icon_row.addStretch()
        self.icon_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.icon_label.setMinimumHeight(120)
        icon_row.addWidget(self.icon_label)
        self.btn_refresh = QtWidgets.QToolButton()
        self.btn_refresh.setText("Refresh")
        self.btn_refresh.setToolTip("Refresh reader status")
        self.btn_refresh.clicked.connect(self.refresh_reader_status)
        icon_row.addWidget(self.btn_refresh)
        icon_row.addStretch()

        # Load icons from packaged resources
        self.icons = {}
        for state, fname in {
            "black": "nfc_black.png",  # no reader connected
            "red":   "nfc_red.png",    # reader present, no card
            "green": "nfc_green.png",  # card present (presence monitor)
        }.items():
            try:
                data = resources.files("anycubic_nfc_qt5.ui.resources").joinpath(fname).read_bytes()
                pm = QtGui.QPixmap()
                pm.loadFromData(data)
                self.icons[state] = pm
            except Exception as e:
                print(f"[WARN] Could not load {fname}: {e}")

        # internal state
        self._icon_state = "black"
        self.reader_available = False
        self.card_present = False

        # === Selection row ===
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)

        left_box = QtWidgets.QGroupBox("Choose filament")
        right_box = QtWidgets.QGroupBox("Choose color")
        row.addWidget(left_box, 1)
        row.addWidget(right_box, 1)

        # Left: filament combo
        self.combo_filament = QtWidgets.QComboBox()
        v_left = QtWidgets.QVBoxLayout(left_box)
        v_left.addWidget(self.combo_filament)

        # Right: color combo + color dot + hex label
        self.combo_color = QtWidgets.QComboBox()
        self.color_dot = ColorDot()
        self.color_hex_label = QtWidgets.QLabel("")
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self.combo_color, 1)
        right_row.addWidget(self.color_dot, 0, QtCore.Qt.AlignVCenter)
        right_row.addWidget(self.color_hex_label, 0, QtCore.Qt.AlignVCenter)
        v_right = QtWidgets.QVBoxLayout(right_box)
        v_right.addLayout(right_row)

        # === SKU Display (prominent) ===
        self.sku_label = QtWidgets.QLabel("", alignment=QtCore.Qt.AlignCenter)
        self.sku_label.setObjectName("skuLabel")
        f = self.sku_label.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 4)
        self.sku_label.setFont(f)
        self.sku_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.sku_label, 0, QtCore.Qt.AlignHCenter)

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
        log_row = QtWidgets.QHBoxLayout()
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)

        self.btn_clear_log = QtWidgets.QToolButton()
        self.btn_clear_log.setText("Clear Log")
        self.btn_clear_log.setToolTip("Clear the log window")
        self.btn_clear_log.clicked.connect(self.clear_log)

        log_row.addWidget(self.output, 1)
        log_row.addWidget(self.btn_clear_log, 0, QtCore.Qt.AlignTop)

        layout.addLayout(log_row)
        self.statusBar().showMessage("Ready")

        # placeholders
        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)
        self._set_color_indicator(None)

        # Load filaments
        try:
            self.by_filament, self.by_sku = load_filaments(None)
            names = sorted(self.by_filament.keys(), key=str.casefold)
            for name in names:
                self.combo_filament.addItem(name)
            self.log(f"Loaded {sum(len(v) for v in self.by_filament.values())} filament records.")
        except Exception as e:
            self.log(f"[Error] Failed to load filaments: {e}")

        # Signals
        self.combo_filament.currentTextChanged.connect(self.on_filament_changed)
        self.combo_color.currentTextChanged.connect(self.on_color_changed)
        self.btn_read.clicked.connect(self.on_read)
        self.btn_write.clicked.connect(self.on_write)
        self.btn_refresh.clicked.connect(self.refresh_reader_status)

        # Initial reader status + auto-refresh (no APDUs)
        self.refresh_reader_status()
        self.reader_timer = QtCore.QTimer(self)
        self.reader_timer.setInterval(2000)           # only checks list_readers()
        self.reader_timer.timeout.connect(self.refresh_reader_status)
        self.reader_timer.start()

        # Start presence monitor (no reading) → toggles green/red
        self._presence_bridge = _QtPresenceBridge()
        self._presence_bridge.presenceChanged.connect(self.on_card_presence_changed)
        self._card_monitor = CardMonitor()
        self._presence_observer = _CardPresenceObserver(self._presence_bridge)
        self._card_monitor.addObserver(self._presence_observer)

        self._update_actions()

    # === UI Helpers ===

    def clear_log(self):
        """Clear the text log."""
        self.output.clear()

    def set_icon_state(self, key: str):
        """Set icon by state key: 'black' (no reader), 'red' (reader no card), 'green' (card present)."""
        pix = self.icons.get(key)
        if not pix or pix.isNull():
            self.icon_label.setText("[missing icon]")
            return
        self.icon_label.setPixmap(pix.scaledToWidth(100, QtCore.Qt.SmoothTransformation))
        self._icon_state = key

    def refresh_reader_status(self):
        """Detect reader presence once and update UI (icon + buttons)."""
        self.reader_available = bool(list_readers())
        if not self.reader_available:
            self.card_present = False
            self.set_icon_state("black")
        else:
            # If a card is present (from presence monitor), keep green; otherwise red
            self.set_icon_state("green" if self.card_present else "red")
        self._update_actions()

    def _set_sku(self, sku: str | None):
        """Update prominent SKU label."""
        self.sku_label.setText(f"SKU: {sku}" if sku else "")

    def log(self, msg: str):
        self.output.appendPlainText(msg)

    def _update_actions(self):
        """Enable/disable buttons based on selection state and reader/card availability."""
        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        reader_ok = self.reader_available
        card_ok = getattr(self, "card_present", False)

        # READ: nur Reader nötig
        self.btn_read.setEnabled(reader_ok)

        # WRITE: Reader + Karte + gültige Auswahl
        self.btn_write.setEnabled(reader_ok and card_ok and filament_ok and color_ok)

    def _set_color_indicator(self, hex_str: str | None):
        """Update the color dot and hex text (expects '#RRGGBB' or None)."""
        if not hex_str:
            self.color_dot.set_color_hex("#000000")
            self.color_hex_label.setText("")
            return
        rgb = normalize_hex(hex_str)
        self.color_dot.set_color_hex(rgb)
        self.color_hex_label.setText(rgb)

    def _select_by_sku(self, sku_read: str) -> bool:
        """Try to preselect filament and color based on SKU (prefers exact match; falls back to base)."""
        # 1) exakte Full-SKU
        rec = self.by_sku.get(sku_read)
        chosen = rec

        # 2) Fallback: über SKU-Basis
        if not chosen:
            base = sku_base(sku_read)
            if base:
                # finde *irgendeinen* Eintrag, dessen SKU mit 'BASE-' beginnt
                for r_sku, r in self.by_sku.items():
                    if r_sku.startswith(base + "-"):
                        chosen = r
                        break

        if not chosen:
            self.log(f"[INFO] Keine passende Konfiguration für SKU '{sku_read}' (Basis='{sku_base(sku_read)}') gefunden.")
            return False

        # Filament auswählen
        filament_name = chosen.filament
        idx_f = self.combo_filament.findText(filament_name, QtCore.Qt.MatchFixedString)
        if idx_f <= 0:
            self.log(f"[INFO] Filament '{filament_name}' nicht in Liste gefunden.")
            return False
        self.combo_filament.setCurrentIndex(idx_f)  # triggert on_filament_changed(), baut Color-Liste

        # Farbe auswählen (Items: Text=color, Data=(sku, hex))
        color_name = chosen.color
        for i in range(1, self.combo_color.count()):
            if self.combo_color.itemText(i) == color_name:
                self.combo_color.setCurrentIndex(i)
                break
        else:
            self.log(f"[INFO] Farbe '{color_name}' nicht in Liste für '{filament_name}'.")
            return False

        return True


    # === Presence callback (no reading) ===
    @QtCore.pyqtSlot(bool)
    def on_card_presence_changed(self, present: bool):
        """React to card insert/remove events without reading any data."""
        self.card_present = present
        if not self.reader_available:
            # Reader might be unplugged; keep black
            self.set_icon_state("black")
        else:
            self.set_icon_state("green" if present else "red")
        self._update_actions()  

    # === Selection handlers ===
    def on_filament_changed(self, filament_name: str):
        """Handle filament selection change."""
        if self.combo_filament.currentIndex() == 0 or filament_name == PLACEHOLDER_FILAMENT:
            set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
            self.combo_color.setEnabled(False)
            self._set_color_indicator(None)
            self._set_sku(None)
            self._update_actions()
            return

        records = self.by_filament.get(filament_name, [])
        self.log(f"Selected filament: {filament_name} ({len(records)} variants)")

        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(True)
        seen = set()
        for rec in records:
            if rec.color not in seen:
                self.combo_color.addItem(rec.color, (rec.sku, rec.color_hex))
                seen.add(rec.color)

        self._set_color_indicator(None)
        self._set_sku(None)
        self._update_actions()

    def on_color_changed(self, color_name: str):
        """Update color dot on color selection."""
        if self.combo_color.currentIndex() == 0 or color_name == PLACEHOLDER_COLOR:
            self._set_color_indicator(None)
            self._set_sku(None)
            self._update_actions()
            return
        data = self.combo_color.currentData()  # (sku, color_hex)
        if data:
            sku, hex_str = data
            self._set_color_indicator(hex_str)
            self._set_sku(sku)
            self.log(f"Selected color: {color_name} [{normalize_hex(hex_str)}], SKU={sku}")
        self._update_actions()

    # === Buttons ===
    def on_read(self):
        """On-demand read: try once; set icon accordingly and log ATR/UID."""
        self.refresh_reader_status()
        if not self.reader_available:
            self.log("[ERROR] No NFC reader connected.")
            return

        conn = connect_first_reader()
        if conn is None:
            self.log("[ERROR] No NFC reader available.")
            self.reader_available = False
            self.set_icon_state("black")
            self._update_actions()
            return

        try:
            conn.connect()  # fails if no card present
            # Icon is already green from presence monitor if a card is present.
            atr = read_atr(conn) or b""
            uid, sw1, sw2 = read_uid(conn)
            if atr:
                self.log(f"[OK] ATR: {' '.join(f'{x:02X}' for x in atr)}")
            if uid is not None:
                self.log(f"[OK] UID: {' '.join(f'{x:02X}' for x in uid)}")
            else:
                self.log("[INFO] UID not available on this reader/card.")

            info = read_anycubic_fields(conn)
            self._last_read_full_sku = info.get("sku") or ""
            nice = interpret_anycubic(info)

            sku = info.get("sku") or ""
            mat = info.get("material") or ""

            if sku:
                self._set_sku(sku)
                self.log(f"[OK] SKU: {sku}")
                self._last_read_full_sku = info.get("sku") or ""
                # Optional: Filament/Color automatisch setzen, falls vorhanden
                if self._select_by_sku(sku):
                    self.log("[OK] Vorauswahl per SKU gesetzt (Filament & Color).")
            else:
                self.log("[INFO] Keine SKU erkannt.")

            if mat:
                self.log(f"[OK] Material: {mat}")

            fr = nice.get("friendly", {})
            if "filament_diameter_mm" in fr:
                self.log(f"[OK] Filament Ø: {fr['filament_diameter_mm']:.2f} mm")
            if "nozzle_temp_min_c" in fr and "nozzle_temp_max_c" in fr:
                self.log(f"[OK] Nozzle-Temp: {fr['nozzle_temp_min_c']}–{fr['nozzle_temp_max_c']} °C")
            if "bed_temp_min_c" in fr and "bed_temp_max_c" in fr:
                self.log(f"[OK] Bed-Temp: {fr['bed_temp_min_c']}–{fr['bed_temp_max_c']} °C")
            if "spool_weight_g" in fr and "spool_weight_kg" in fr:
                self.log(f"[OK] Spulen-Gewicht: {fr['spool_weight_g']} g ({fr['spool_weight_kg']:.3f} kg)")
            if "unknown_p30_b" in fr:
                self.log(f"[DBG] p30_b (unbekannt): {fr['unknown_p30_b']}")



        except Exception:
            # No card on it → ensure red (unless reader gone)
            if self.reader_available:
                self.set_icon_state("red")
            self.log("[INFO] No card detected. Place a tag on the reader and try again.")
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass
            # Reader status will keep being updated by presence monitor / refresh

    def on_write(self):
        """Guarded write: require reader and valid selections."""
        self.refresh_reader_status()
        if not self.reader_available:
            self.log("[ERROR] No NFC reader connected.")
            return
        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        if not (filament_ok and color_ok):
            self.log("[INFO] Please select filament and color before writing.")
            return
        self.log("[INFO] WRITE NFC clicked (write logic not implemented yet)")

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Detach presence observer on close."""
        try:
            if hasattr(self, "_card_monitor") and hasattr(self, "_presence_observer"):
                try:
                    self._card_monitor.deleteObserver(self._presence_observer)
                except Exception:
                    pass
        finally:
            super().closeEvent(event)

def run_app():
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())