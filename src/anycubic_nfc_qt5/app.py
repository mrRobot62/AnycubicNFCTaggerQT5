# src/anycubic_nfc_qt5/app.py
import sys
import time
import re
from pathlib import Path
from PyQt5 import QtWidgets, QtGui, QtCore
from importlib import resources
from smartcard.Exceptions import NoCardException

from .config.filaments import load_filaments
from anycubic_nfc_qt5.nfc.pcsc import (
    list_readers,
    connect_first_reader,
    read_atr,
    read_uid,
    read_anycubic_fields,
    interpret_anycubic,
    write_anycubic_basic
)

# pyscard presence monitor (no APDU, just insert/remove)
from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.Exceptions import NoCardException

PLACEHOLDER_FILAMENT = "select filament"
PLACEHOLDER_COLOR = "select color"


# ------------------------- Helpers (module-level) -------------------------

def sku_base(sku: str) -> str:
    """Return alphanumeric part before '-', e.g. 'AHHSCG-101' -> 'AHHSCG'."""
    if not sku:
        return ""
    head = sku.split("-", 1)[0]
    return re.sub(r"[^A-Za-z0-9]", "", head)


def normalize_hex(hex_str: str) -> str:
    """Convert '#RRGGBBAA' -> '#RRGGBB'. Keep '#RRGGBB' unchanged."""
    s = (hex_str or "").strip()
    if not s.startswith("#"):
        return "#000000"
    if len(s) >= 9:
        return s[:7].upper()
    if len(s) == 7:
        return s.upper()
    return "#000000"


def color_core6(hex_str: str) -> str:
    """Return '#RRGGBB' uppercase for comparisons (drop alpha)."""
    return normalize_hex(hex_str).upper()


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


def _normalize_hex_full(h: str) -> str:
    """Return '#RRGGBBAA' uppercase if possible; accept '#RRGGBB' -> '#RRGGBBFF'."""
    s = (h or "").strip()
    if not s.startswith("#"):
        return "#000000FF"
    s = s.upper()
    if len(s) == 7:
        return s + "FF"
    if len(s) >= 9:
        return s[:9]
    return "#000000FF"


def update_color_for_sku(sku: str, new_hex: str, file_path: Path | None = None) -> bool:
    """
    Update the color hex for a given full SKU in ac_filaments.ini.
    Returns True on success, False on failure.
    """
    try:
        ini_path = (file_path if file_path is not None
                    else Path(__file__).parent / "ac_filaments.ini")
        text = ini_path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        changed = False
        new_hex_full = _normalize_hex_full(new_hex)

        out_lines = []
        for ln in lines:
            parts = [p.strip() for p in ln.split(";")]
            if not parts or parts[0] != sku:
                out_lines.append(ln)
                continue
            while len(parts) < 4:
                parts.append("")
            parts[3] = new_hex_full
            out_lines.append(";".join(parts))
            changed = True

        if not changed:
            return False

        ini_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


# ------------------------------ UI Widgets --------------------------------

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


# ------------------------------- MainWindow --------------------------------

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AnycubicNFCTaggerQT5")
        self.resize(620, 400)

        self._filament_ini_path = Path(__file__).parent / "config" / "ac_filaments.ini"
        self._last_read_full_sku = ""

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

        # === Log output + Clear ===
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

        # READ: reader required
        self.btn_read.setEnabled(reader_ok)

        # WRITE: reader + card + valid selection
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
        """Preselect filament & color strictly by SKU base (ignore numeric part)."""
        base = sku_base(sku_read)
        if not base:
            self.log(f"[INFO] Keine gültige SKU-Basis für '{sku_read}' ermittelt.")
            return False

        sku_key, chosen = self._find_ini_record_for_base(base)
        if not chosen:
            self.log(f"[INFO] Keine Konfiguration für SKU-Basis '{base}' gefunden.")
            return False

        # Filament auswählen
        filament_name = chosen.filament
        idx_f = self.combo_filament.findText(filament_name, QtCore.Qt.MatchFixedString)
        if idx_f <= 0:
            self.log(f"[INFO] Filament '{filament_name}' nicht in Liste gefunden.")
            return False
        self.combo_filament.setCurrentIndex(idx_f)  # triggert on_filament_changed()

        # Farbe auswählen (Items: Text=color, Data=(sku, hex))
        color_name = chosen.color
        for i in range(1, self.combo_color.count()):
            if self.combo_color.itemText(i) == color_name:
                self.combo_color.setCurrentIndex(i)
                break
        else:
            self.log(f"[INFO] Farbe '{color_name}' nicht in Liste für '{filament_name}'.")
            return False

        self.log(f"[DBG] Vorauswahl anhand SKU-Basis '{base}' (Match: {sku_key}).")
        return True

    def _reload_filaments(self, reseat_by_sku: bool = True):
        """Reload ac_filaments.ini into memory and refresh combos.
        If reseat_by_sku is True and a last-read full SKU exists,
        try to auto-select via SKU base; otherwise restore previous selections."""
        # remember current selections (by text)
        prev_filament = self.combo_filament.currentText() if self.combo_filament.currentIndex() > 0 else None
        prev_color = self.combo_color.currentText() if self.combo_color.currentIndex() > 0 else None

        try:
            self.by_filament, self.by_sku = load_filaments(None)
        except Exception as e:
            self.log(f"[ERROR] Reload filaments failed: {e}")
            return

        # rebuild filament combo
        self.combo_filament.blockSignals(True)
        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        names = sorted(self.by_filament.keys(), key=str.casefold)
        for name in names:
            self.combo_filament.addItem(name)
        self.combo_filament.blockSignals(False)

        # default: reset color box
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)
        self._set_color_indicator(None)

        # reseat preference
        if reseat_by_sku and getattr(self, "_last_read_full_sku", ""):
            if self._select_by_sku(self._last_read_full_sku):
                # _select_by_sku setzt die Farbe & rebuildet die Color-Combo
                self._update_actions()
                return

        # try to restore previous selection by text
        if prev_filament:
            idx_f = self.combo_filament.findText(prev_filament, QtCore.Qt.MatchFixedString)
            if idx_f > 0:
                self.combo_filament.setCurrentIndex(idx_f)  # triggers on_filament_changed -> rebuilds color combo
                if prev_color:
                    idx_c = self.combo_color.findText(prev_color, QtCore.Qt.MatchFixedString)
                    if idx_c > 0:
                        self.combo_color.setCurrentIndex(idx_c)
                        # refresh color indicator from current item data
                        data = self.combo_color.currentData()
                        if data and len(data) >= 2:
                            self._set_color_indicator(data[1])

        self._update_actions()

    def _append_ini_line(self, sku: str, filament: str, color_name: str, color_hex: str) -> bool:
        """
        Append a new line to ac_filaments.ini in the form:
        SKU;FILAMENT;COLOR;#RRGGBBAA
        Returns True on success, False on failure.
        """
        try:
            ini_path = self._filament_ini_path
            # normalize fields
            sku = (sku or "").strip()
            filament = (filament or "").strip()
            color_name = (color_name or "").strip()
            color_hex = (color_hex or "").strip().upper()
            if not color_hex.startswith("#"):
                color_hex = "#" + color_hex
            if len(color_hex) == 7:
                color_hex += "FF"

            if not (sku and filament and color_name):
                self.log("[ERROR] _append_ini_line: missing required fields.")
                return False

            new_line = f"{sku};{filament};{color_name};{color_hex}"

            with open(ini_path, "a", encoding="utf-8") as f:
                # Ensure newline if file doesn’t end with one
                f.write(("\n" if not str(ini_path.read_text()).endswith("\n") else "") + new_line + "\n")

            self.log(f"[DBG] Added new line to INI: {new_line}")
            return True
        except Exception as e:
            self.log(f"[ERROR] _append_ini_line failed: {e}")
            return False

    def _find_ini_record_for_base(self, base: str):
        """Find config record by SKU base only (e.g. 'AHHSCG'), ignoring the numeric suffix.
        Prefers a candidate whose color equals the currently selected color; otherwise returns the first match.
        Returns (sku_key, rec) or (None, None)."""
        if not base:
            return (None, None)
        candidates = [(k, v) for (k, v) in self.by_sku.items() if k.startswith(base + "-")]
        if not candidates:
            self.log(f"[DBG] _find_ini_record_for_base: no candidates for base '{base}'")
            return (None, None)

        # Prefer the currently selected color if any
        cur_color = None
        if self.combo_color.currentIndex() > 0:
            cur_color = self.combo_color.currentText().strip()
        if cur_color:
            for k, v in candidates:
                if (v.color or "").strip() == cur_color:
                    return (k, v)

        # Fallback: first candidate
        return candidates[0]

    # === Presence callback (no reading) ===
    @QtCore.pyqtSlot(bool)
    def on_card_presence_changed(self, present: bool):
        """React to card insert/remove events without reading any data."""
        self.card_present = present
        if not self.reader_available:
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
        """On-demand read: connect once; log ATR/UID; parse Anycubic; compare/update INI color."""
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

        # 1) Nur den Verbindungsaufbau gezielt abfangen
        try:
            conn.connect()  # wirft NoCardException, wenn keine Karte aufgelegt ist
        except NoCardException:
            if self.reader_available:
                self.set_icon_state("red")
            self.log("[INFO] No card detected. Place a tag on the reader and try again.")
            try:
                conn.disconnect()
            except Exception:
                pass
            return
        except Exception as e:
            # Unerwarteter Fehler beim Verbinden
            self.log(f"[ERROR] Connect failed: {e}")
            try:
                conn.disconnect()
            except Exception:
                pass
            return

        # 2) Ab hier ist die Karte verbunden – alle anderen Fehler NICHT als „No card“ melden
        try:
            # ATR/UID
            atr = read_atr(conn) or b""
            uid, sw1, sw2 = read_uid(conn)
            if atr:
                self.log(f"[OK] ATR: {' '.join(f'{x:02X}' for x in atr)}")
            if uid is not None:
                self.log(f"[OK] UID: {' '.join(f'{x:02X}' for x in uid)}")
            else:
                self.log("[INFO] UID not available on this reader/card.")

            # Anycubic-Rohdaten
            info = read_anycubic_fields(conn)

            # --- Farbe vom Tag vs. INI vergleichen & ggf. speichern (Basis-Suche) ---
            self._last_read_full_sku = info.get("sku") or ""
            tag_hex_full = (info.get("color_hex") or "").upper()
            base = sku_base(self._last_read_full_sku)

            if base and tag_hex_full:
                sku_key, ini_rec = self._find_ini_record_for_base(base)
                if not ini_rec:
                    msg = (f"No INI entry for SKU base '{base}'.\n"
                        f"Create new INI entry for full SKU '{self._last_read_full_sku}' with tag color {tag_hex_full}?")
                    ans = QtWidgets.QMessageBox.question(
                        self, "Add new INI entry?", msg,
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No
                    )
                    if ans == QtWidgets.QMessageBox.Yes:
                        filament_name = self.combo_filament.currentText().strip() if self.combo_filament.currentIndex() > 0 else ((info.get("material") or "").strip() or "Unknown")
                        color_name = self.combo_color.currentText().strip() if self.combo_color.currentIndex() > 0 else "Unknown"
                        if self._append_ini_line(self._last_read_full_sku, filament_name, color_name, tag_hex_full):
                            self.log(f"[OK] Added INI entry: {self._last_read_full_sku};{filament_name};{color_name};{tag_hex_full}")
                            self._reload_filaments(reseat_by_sku=True)
                            self.log(f"[OK] Reload INI: {self._last_read_full_sku};{filament_name};{color_name};{tag_hex_full}")

                        else:
                            self.log("[ERROR] Could not add new INI entry.")
                else:
                    ini_rgb = color_core6(ini_rec.color_hex or "")
                    tag_rgb = color_core6(tag_hex_full)
                    if ini_rgb != tag_rgb:
                        msg = (f"Detected different color for SKU base '{base}' (match: {sku_key}):\n"
                            f"- Tag: {tag_hex_full}\n"
                            f"- INI: {ini_rec.color_hex}\n\n"
                            "Update INI color for this SKU entry?")
                        ans = QtWidgets.QMessageBox.question(
                            self, "Update color in INI?", msg,
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            QtWidgets.QMessageBox.No
                        )
                        if ans == QtWidgets.QMessageBox.Yes:
                            ok = update_color_for_sku(
                                sku=sku_key,
                                new_hex=tag_hex_full,
                                file_path=self._filament_ini_path
                            )
                            if ok:
                                self.log(f"[OK] Updated INI color for {sku_key} -> {tag_hex_full}")
                                ini_rec.color_hex = tag_hex_full
                                if self.combo_color.currentIndex() > 0:
                                    data = self.combo_color.currentData()
                                    if data and data[0] == sku_key:
                                        self.combo_color.setItemData(
                                            self.combo_color.currentIndex(),
                                            (sku_key, tag_hex_full)
                                        )
                                        self._set_color_indicator(tag_hex_full)
                            else:
                                self.log("[ERROR] Failed to update ac_filaments.ini — check path/permissions.")
                    else:
                        self.log(f"[DBG] color equal (RGB): INI vs Tag for base '{base}' (match: {sku_key})")
            else:
                if not base:
                    self.log("[DBG] skip color compare: no SKU base")
                if not tag_hex_full:
                    self.log("[DBG] skip color compare: no color_hex on tag")

            # Anzeige/Auto-Select
            from anycubic_nfc_qt5.nfc.pcsc import interpret_anycubic
            nice = interpret_anycubic(info)
            sku = info.get("sku") or ""
            mat = info.get("material") or ""
            if sku:
                self._set_sku(sku)
                self.log(f"[OK] SKU: {sku}")
                if self._select_by_sku(sku):
                    self.log("[OK] Vorauswahl per SKU-Basis gesetzt (Filament & Color).")
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

        except Exception as e:
            # Irgendein *anderer* Fehler beim Lesen/Parsen → als Error loggen,
            # NICHT als "No card" (die Karte ist ja verbunden)
            self.log(f"[ERROR] Read failed: {e}")
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass


    def on_write(self):
        """Write basic Anycubic fields to the tag currently present."""
        # Reader + UI state checks
        self.refresh_reader_status()
        if not self.reader_available:
            self.log("[ERROR] No NFC reader connected.")
            return
        if not self.card_present:
            self.log("[INFO] No card detected. Place a tag on the reader first.")
            return

        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        if not (filament_ok and color_ok):
            self.log("[INFO] Please select filament and color before writing.")
            return

        # Collect values from UI
        material = self.combo_filament.currentText().strip()  # e.g., 'PLA High Speed'
        color_name = self.combo_color.currentText().strip()
        data = self.combo_color.currentData()  # (sku, color_hex)
        if not data or len(data) < 2:
            self.log("[ERROR] Internal error: no SKU/color data attached to color item.")
            return

        full_sku = data[0] or ""          # full SKU (e.g. 'AHHSCG-101')
        color_hex_full = (data[1] or "").upper()  # may be '#RRGGBB' or '#RRGGBBAA'
        if color_hex_full and len(color_hex_full) == 7:
            color_hex_full += "FF"  # ensure alpha

        manufacturer = "AC"  # default for now

        # Connect to reader
        conn = connect_first_reader()
        if conn is None:
            self.log("[ERROR] No NFC reader available.")
            self.reader_available = False
            self.set_icon_state("black")
            self._update_actions()
            return

        try:
            try:
                conn.connect()
            except NoCardException:
                self.set_icon_state("red")
                self.log("[INFO] No card detected. Place a tag on the reader and try again.")
                return

            # Perform write
            self.log(f"[INFO] Writing tag… SKU={full_sku}, Material={material}, Color={color_hex_full}, Manufacturer={manufacturer}")
            res = write_anycubic_basic(
                conn,
                sku=full_sku,
                manufacturer=manufacturer,
                material=material,
                color_hex=color_hex_full,
            )

            # Summarize results
            ok_sku    = res.get("p05_sku", False)
            ok_manu   = res.get("p0A_manu", False)
            ok_mat    = res.get("p0F_mat", False)
            ok_color  = res.get("p14_color", False)

            self.log(f"[{'OK' if ok_sku else 'ERR'}] Write p05 (SKU)")
            self.log(f"[{'OK' if ok_manu else 'ERR'}] Write p10 (Manufacturer)")
            self.log(f"[{'OK' if ok_mat else 'ERR'}] Write p15 (Material)")
            self.log(f"[{'OK' if ok_color else 'ERR'}] Write p20 (Color)")

            if all((ok_sku, ok_manu, ok_mat, ok_color)):
                self.log("[OK] Basic data written successfully.")
            else:
                self.log("[WARN] Some fields could not be written. The tag may be locked or protected.")

            # Optional: sofort verifizieren (READ erneut ausführen)
            # -> du kannst hier `self.on_read()` rufen, wenn du die Werte gleich prüfen willst
            # self.on_read()

        except Exception as e:
            self.log(f"[ERROR] Write failed: {e}")
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

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