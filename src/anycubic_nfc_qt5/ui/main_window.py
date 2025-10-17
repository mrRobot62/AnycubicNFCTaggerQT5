# src/anycubic_nfc_qt5/ui/main_window.py
from __future__ import annotations

from pathlib import Path
from PyQt5 import QtWidgets, QtGui, QtCore
from importlib import resources
from smartcard.Exceptions import NoCardException
import sys
import traceback

from ..constants import PLACEHOLDER_FILAMENT, PLACEHOLDER_COLOR
from ..utils.placeholders import set_placeholder
from ..utils.colors import normalize_hex, color_core6
from ..utils.sku import sku_base
from ..config.filaments import load_filaments
from ..config.ini_utils import update_color_for_sku, append_ini_line
from ..nfc.presence import QtPresenceBridge, start_presence_monitor
from ..nfc.pcsc import (
    list_readers,
    connect_first_reader,
    read_atr,
    read_uid,
    read_anycubic_fields,
    interpret_anycubic,
    write_anycubic_basic,
    write_raw_pages,
    clear_user_area,
)

# unified field mapping helpers (multi-page aware)
from .nfc_fields import (
    P,                 # logical field spans
    map_ascii_span,    # map long ASCII strings to PageSpan
    map_color_rgba,    # map hex color to RGBA page
    map_u16,           # map u16 numbers to a page
)

from .widgets.color_dot import ColorDot
from .docks.page_editor_dock import PageEditorDock


# ---------- local helpers ----------
def _ascii4(s: str) -> bytes:
    """Return first 4 ASCII bytes (padded with 00)."""
    b = (s or "").encode("ascii", errors="ignore")[:4]
    if len(b) < 4:
        b = b + b"\x00" * (4 - len(b))
    return b


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, title: str, version: str):
        super().__init__()
        self.setWindowTitle(f"{title} - {version}")
        self.resize(1100, 680)

        self._filament_ini_path = Path(__file__).resolve().parents[1] / "config" / "ac_filaments.ini"
        self._last_read_full_sku = ""

        # === central UI ===
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # === NFC icon + refresh ===
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

        # icons
        self.icons = {}
        for key, fname in {
            "black": "nfc_black.png",
            "red": "nfc_red.png",
            "green": "nfc_green.png",
        }.items():
            try:
                data = resources.files("anycubic_nfc_qt5.ui.resources").joinpath(fname).read_bytes()
                pm = QtGui.QPixmap()
                pm.loadFromData(data)
                self.icons[key] = pm
            except Exception as e:
                print(f"[WARN] Could not load icon {fname}: {e}", file=sys.stderr)

        self._icon_state = "black"
        self.reader_available = False
        self.card_present = False

        # === filament/color selection ===
        row = QtWidgets.QHBoxLayout()
        layout.addLayout(row)

        left_box = QtWidgets.QGroupBox("Choose filament")
        right_box = QtWidgets.QGroupBox("Choose color")
        row.addWidget(left_box, 1)
        row.addWidget(right_box, 1)

        self.combo_filament = QtWidgets.QComboBox()
        v_left = QtWidgets.QVBoxLayout(left_box)
        v_left.addWidget(self.combo_filament)

        self.combo_color = QtWidgets.QComboBox()
        self.color_dot = ColorDot()
        self.color_hex_label = QtWidgets.QLabel("")
        right_row = QtWidgets.QHBoxLayout()
        right_row.addWidget(self.combo_color, 1)
        right_row.addWidget(self.color_dot)
        right_row.addWidget(self.color_hex_label)
        v_right = QtWidgets.QVBoxLayout(right_box)
        v_right.addLayout(right_row)

        # === SKU display ===
        self.sku_label = QtWidgets.QLabel("", alignment=QtCore.Qt.AlignCenter)
        f = self.sku_label.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 4)
        self.sku_label.setFont(f)
        self.sku_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.sku_label, 0, QtCore.Qt.AlignHCenter)

        # === buttons ===
        btn_row = QtWidgets.QHBoxLayout()
        layout.addLayout(btn_row)
        self.btn_read = QtWidgets.QPushButton("READ NFC")
        self.btn_write = QtWidgets.QPushButton("WRITE NFC")
        self.btn_pages = QtWidgets.QPushButton("Page Editor")
        self.btn_reset = QtWidgets.QToolButton()
        self.btn_reset.setText("Reset combos")
        self.btn_reset.setToolTip("Reset filament & color selection")

        btn_row.addStretch()
        btn_row.addWidget(self.btn_read)
        btn_row.addWidget(self.btn_write)
        btn_row.addWidget(self.btn_pages)
        btn_row.addStretch()

        # === log area ===
        log_row = QtWidgets.QHBoxLayout()
        layout.addLayout(log_row)
        self.output = QtWidgets.QPlainTextEdit()
        self.output.setReadOnly(True)
        self.btn_clear_log = QtWidgets.QToolButton()
        self.btn_clear_log.setText("Clear Log")
        self.btn_clear_log.clicked.connect(self.clear_log)

        right_col = QtWidgets.QVBoxLayout()
        right_col.addWidget(self.btn_clear_log, 0, QtCore.Qt.AlignTop)
        right_col.addWidget(self.btn_reset, 0, QtCore.Qt.AlignTop)
        right_col.addStretch()

        log_row.addWidget(self.output, 1)
        log_row.addLayout(right_col, 0)

        self.statusBar().showMessage("Ready")

        # placeholders
        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)
        self._set_color_indicator(None)

        # load filaments
        try:
            self.by_filament, self.by_sku = load_filaments(None)
            for name in sorted(self.by_filament.keys(), key=str.casefold):
                self.combo_filament.addItem(name)
            self.log(f"Loaded {sum(len(v) for v in self.by_filament.values())} filament records.")
        except Exception as e:
            self.log(f"[Error] Failed to load filaments: {e}")
            self.log_exception()

        # Page Editor dock
        self.page_dock = PageEditorDock(self, max_page=63)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.page_dock)
        self.page_dock.hide()
        self.btn_pages.clicked.connect(self._toggle_page_dock)
        self.page_dock.simulateRequested.connect(self._on_editor_simulate)
        self.page_dock.writePagesRequested.connect(self._on_editor_write)
        self.page_dock.deleteUserAreaRequested.connect(self._on_editor_delete_user_area)
        self.page_dock.clearUiRequested.connect(self.on_reset_selection)

        # signals
        self.combo_filament.currentTextChanged.connect(self.on_filament_changed)
        self.combo_color.currentTextChanged.connect(self.on_color_changed)
        self.btn_read.clicked.connect(self.on_read)
        self.btn_write.clicked.connect(self.on_write)
        self.btn_refresh.clicked.connect(self.refresh_reader_status)
        self.btn_reset.clicked.connect(self.on_reset_selection)

        # monitor
        self.refresh_reader_status()
        self.reader_timer = QtCore.QTimer(self)
        self.reader_timer.setInterval(2000)
        self.reader_timer.timeout.connect(self.refresh_reader_status)
        self.reader_timer.start()

        self._presence_bridge = QtPresenceBridge()
        self._presence_bridge.presenceChanged.connect(self.on_card_presence_changed)
        self._card_monitor, self._presence_observer = start_presence_monitor(self._presence_bridge)

        self._update_actions()

    # ---------- basic helpers ----------
    def clear_log(self):
        self.output.clear()

    def log(self, msg: str):
        self.output.appendPlainText(msg)

    def log_exception(self, prefix: str = "[ERROR]"):
        """Append full traceback of the active exception to the log window and stderr."""
        exc = traceback.format_exc()
        self.log(f"{prefix}\n{exc}")
        print(exc, file=sys.stderr)

    def set_icon_state(self, key: str):
        pix = self.icons.get(key)
        if pix:
            self.icon_label.setPixmap(pix.scaledToWidth(100, QtCore.Qt.SmoothTransformation))
            self._icon_state = key

    def refresh_reader_status(self):
        self.reader_available = bool(list_readers())
        if not self.reader_available:
            self.card_present = False
            self.set_icon_state("black")
        else:
            self.set_icon_state("green" if self.card_present else "red")
        self._update_actions()

    def _set_color_indicator(self, hex_str: str | None):
        if not hex_str:
            self.color_dot.set_color_hex("#000000")
            self.color_hex_label.setText("")
            return
        rgb = normalize_hex(hex_str)
        self.color_dot.set_color_hex(rgb)
        self.color_hex_label.setText(rgb)

    def _set_sku(self, sku: str | None):
        self.sku_label.setText(f"SKU: {sku}" if sku else "")

    # ---------- presence ----------
    @QtCore.pyqtSlot(bool)
    def on_card_presence_changed(self, present: bool):
        self.card_present = present
        if not self.reader_available:
            self.set_icon_state("black")
        else:
            self.set_icon_state("green" if present else "red")
        self._update_actions()

    def _update_actions(self):
        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        reader_ok = self.reader_available
        card_ok = getattr(self, "card_present", False)
        self.btn_read.setEnabled(reader_ok)
        self.btn_write.setEnabled(reader_ok and card_ok and filament_ok and color_ok)
        self.btn_pages.setEnabled(reader_ok)

    # ---------- selection handlers ----------
    def on_filament_changed(self, filament_name: str):
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
        if self.combo_color.currentIndex() == 0 or color_name == PLACEHOLDER_COLOR:
            self._set_color_indicator(None)
            self._set_sku(None)
            self._update_actions()
            return

        data = self.combo_color.currentData()  # (sku, color_hex)
        if not data:
            return

        sku, hex_str = data
        self._set_color_indicator(hex_str)
        self._set_sku(sku)
        self.log(f"Selected color: {color_name} [{normalize_hex(hex_str)}], SKU={sku}")

        # Prefill PageEditorDock with current selection (multi-page aware; non-destructive)
        material = self.combo_filament.currentText().strip()
        manufacturer = "AC"
        color_full = (hex_str or "").upper()
        if color_full and len(color_full) == 7:
            color_full += "FF"

        staged = {}
        staged.update(map_ascii_span(P.SKU, sku))
        staged.update(map_ascii_span(P.MANUFACTURER, manufacturer, max_pages=1))
        staged.update(map_ascii_span(P.MATERIAL, material))
        staged.update(map_color_rgba(P.COLOR, color_full))

        try:
            self.page_dock.stage_pages(staged, mark_changed=False)
        except Exception:
            self.log_exception()

        self._update_actions()

    # ---------- NFC: READ ----------
    def on_read(self):
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
            try:
                conn.connect()
            except NoCardException:
                if self.reader_available:
                    self.set_icon_state("red")
                self.log("[INFO] No card detected. Place a tag on the reader and try again.")
                return

            # ATR/UID
            atr = read_atr(conn) or b""
            uid, _, _ = read_uid(conn)
            if atr:
                self.log(f"[OK] ATR: {' '.join(f'{x:02X}' for x in atr)}")
            if uid is not None:
                self.log(f"[OK] UID: {' '.join(f'{x:02X}' for x in uid)}")
            else:
                self.log("[INFO] UID not available on this reader/card.]")

            # Anycubic fields
            info = read_anycubic_fields(conn)

            self._last_read_full_sku = info.get("sku") or ""
            tag_hex_full = (info.get("color_hex") or "").upper()
            base = sku_base(self._last_read_full_sku)

            # Compare tag color with INI (by SKU base)
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
                                sku=sku_key, new_hex=tag_hex_full, file_path=self._filament_ini_path
                            )
                            if ok:
                                self.log(f"[OK] Updated INI color for {sku_key} -> {tag_hex_full}")
                                ini_rec.color_hex = tag_hex_full
                            else:
                                self.log("[ERROR] Failed to update ac_filaments.ini — check path/permissions.]")
                    else:
                        self.log(f"[DBG] color equal (RGB): INI vs Tag for base '{base}' (match: {sku_key})")
            else:
                if not base:
                    self.log("[DBG] skip color compare: no SKU base")
                if not tag_hex_full:
                    self.log("[DBG] skip color compare: no color_hex on tag]")

            # ---- Anzeige / Auto-Select / Prefill ----
            try:
                self.log("[DBG] interpret_anycubic…")
                nice = interpret_anycubic(info) or {}
                sku = (info.get("sku") or "").strip()
                mat = (info.get("material") or "").strip()
                raw_color = (info.get("color_hex") or "").strip()

                if sku:
                    self._set_sku(sku)
                    self.log(f"[OK] SKU: {sku}")
                    try:
                        if self._select_by_sku(sku):
                            self.log("[OK] Vorauswahl per SKU-Basis gesetzt (Filament & Color).")
                        else:
                            self.log("[DBG] _select_by_sku() returned False.")
                    except Exception as e:
                        self.log(f"[ERROR] _select_by_sku failed: {e}")
                        self.log_exception()
                else:
                    self.log("[INFO] Keine SKU erkannt.]")

                if mat:
                    self.log(f"[OK] Material: {mat}]")

                # Color: log + indicator + stage into editor (RGBA), non-destructive
                if raw_color:
                    self.log(f"[OK] Color (tag): {raw_color}]")
                    self._set_color_indicator(raw_color)
                    rgba = raw_color.upper()
                    if len(rgba) == 7:  # "#RRGGBB" -> add alpha
                        rgba += "FF"
                else:
                    rgba = ""

                staged = {}
                staged.update(map_ascii_span(P.SKU, sku))
                staged.update(map_ascii_span(P.MANUFACTURER, info.get("manufacturer") or "AC", max_pages=1))
                staged.update(map_ascii_span(P.MATERIAL, mat))
                if rgba:
                    staged.update(map_color_rgba(P.COLOR, rgba))

                if "nozzle_temp_min_c" in info:
                    staged.update(map_u16(P.NOZZLE_MIN, int(info["nozzle_temp_min_c"])))
                if "nozzle_temp_max_c" in info:
                    staged.update(map_u16(P.NOZZLE_MAX, int(info["nozzle_temp_max_c"])))
                if "bed_temp_min_c" in info:
                    staged.update(map_u16(P.BED_MIN, int(info["bed_temp_min_c"])))
                if "bed_temp_max_c" in info:
                    staged.update(map_u16(P.BED_MAX, int(info["bed_temp_max_c"])))
                if "spool_weight_g" in info:
                    staged.update(map_u16(P.WEIGHT_G, int(info["spool_weight_g"])))
                if "filament_diameter_mm" in info:
                    try:
                        staged.update(map_u16(P.DIAMETER_CENTI, int(round(float(info["filament_diameter_mm"]) * 100))))
                    except Exception:
                        pass

                self.page_dock.stage_pages(staged, mark_changed=False)

            except Exception as e:
                self.log(f"[WARN] Prefill dock failed: {e}]")
                self.log_exception()

        except Exception as e:
            self.log(f"[ERROR] Read failed: {e}]")
            self.log_exception()
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

    # ---------- NFC: WRITE (basic Anycubic) ----------
    def on_write(self):
        self.refresh_reader_status()
        if not self.reader_available:
            self.log("[ERROR] No NFC reader connected.]")
            return
        if not self.card_present:
            self.log("[INFO] No card detected. Place a tag on the reader first.]")
            return

        filament_ok = self.combo_filament.currentIndex() > 0
        color_ok = self.combo_color.isEnabled() and self.combo_color.currentIndex() > 0
        if not (filament_ok and color_ok):
            self.log("[INFO] Please select filament and color before writing.]")
            return

        material = self.combo_filament.currentText().strip()
        data = self.combo_color.currentData()  # (sku, color_hex)
        if not data or len(data) < 2:
            self.log("[ERROR] Internal error: no SKU/color data attached to color item.]")
            return

        full_sku = data[0] or ""
        color_hex_full = (data[1] or "").upper()
        if color_hex_full and len(color_hex_full) == 7:
            color_hex_full += "FF"

        manufacturer = "AC"  # default

        conn = connect_first_reader()
        if conn is None:
            self.log("[ERROR] No NFC reader available.]")
            self.reader_available = False
            self.set_icon_state("black")
            self._update_actions()
            return

        try:
            try:
                conn.connect()
            except NoCardException:
                self.set_icon_state("red")
                self.log("[INFO] No card detected. Place a tag on the reader and try again.]")
                return

            self.log(f"[INFO] Writing tag… SKU={full_sku}, Material={material}, Color={color_hex_full}, Manufacturer={manufacturer}]")
            res = write_anycubic_basic(
                conn,
                sku=full_sku,
                manufacturer=manufacturer,
                material=material,
                color_hex=color_hex_full,
            )

            for key, ok in res.items():
                self.log(f"[{'OK' if ok else 'ERR'}] Write {key}]")

            if all(res.values()):
                self.log("[OK] Basic data written successfully.]")
            else:
                self.log("[WARN] Some fields could not be written. The tag may be locked or protected.]")

        except Exception as e:
            self.log(f"[ERROR] Write failed: {e}]")
            self.log_exception()
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

    # ---------- Page Editor Dock ----------
    def _toggle_page_dock(self):
        if self.page_dock.isVisible():
            self.page_dock.hide()
        else:
            self.page_dock.show()
            self.page_dock.raise_()

    @QtCore.pyqtSlot(dict)
    def _on_editor_simulate(self, payload: dict):
        pages = payload.get("pages", {})
        if not pages:
            self.log("[SIM] Nothing to simulate.")
            return

        # helper: ASCII-4 aus 4 Bytes (nicht druckbare -> '.')
        def _ascii4(b4: bytes) -> str:
            b4 = (b4 or b"")[:4]
            b4 = b4 + b"\x00" * (4 - len(b4))
            return "".join(chr(x) if 32 <= x < 127 else "." for x in b4)

        self.log("---- START (HEX) --------------")
        for p in sorted(pages.keys()):
            b4 = (pages[p] or b"")[:4]
            b4 = b4 + b"\x00" * (4 - len(b4))
            hex_line = " ".join(f"{x:02X}" for x in b4)
            asc_line = _ascii4(b4)
            # genau das gewünschte Format (ohne Page-ID)
            self.log(f"p{p:02d}: | {hex_line} | {asc_line}")
        self.log("---- END ----------------------")

    @QtCore.pyqtSlot(dict)
    def _on_editor_write(self, payload: dict):
        if not (self.reader_available and self.card_present):
            self.log("[INFO] No card or reader.")
            return
        pages = payload.get("pages", {})
        if not pages:
            self.log("[INFO] No pages to write.")
            return

        conn = connect_first_reader()
        if conn is None:
            self.log("[ERROR] No NFC reader available.")
            return

        try:
            conn.connect()
            for start, data in self._group_pages(pages):
                self.log(f"[INFO] Writing {len(data)//4} page(s) from 0x{start:02X}")
                res = write_raw_pages(conn, start_page=start, data_bytes=data)
                if isinstance(res, dict):
                    oks = [f"0x{k:02X}" for k, v in res.items() if v]
                    ers = [f"0x{k:02X}" for k, v in res.items() if not v]
                    if oks: self.log(f"[OK] {', '.join(oks)}")
                    if ers: self.log(f"[ERR] {', '.join(ers)}")
                else:
                    self.log("[OK] Raw write completed." if res else "[ERR] Raw write failed.")
        except Exception as e:
            self.log(f"[ERROR] Editor write failed: {e}")
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

    @QtCore.pyqtSlot()
    def _on_editor_delete_user_area(self):
        if not (self.reader_available and self.card_present):
            self.log("[INFO] No card or reader.")
            return
        ret = QtWidgets.QMessageBox.question(
            self, "Confirm erase",
            "Clear entire USER AREA (set to 0x00)?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if ret != QtWidgets.QMessageBox.Yes:
            return

        conn = connect_first_reader()
        if conn is None:
            self.log("[ERROR] No NFC reader available.")
            return
        try:
            conn.connect()
            self.log("[INFO] Reset USER AREA …")
            res = clear_user_area(conn)
            oks = [f"0x{k:02X}" for k, v in res.items() if v]
            ers = [f"0x{k:02X}" for k, v in res.items() if not v]
            if oks: self.log(f"[OK] Cleared pages: {', '.join(oks)}")
            if ers: self.log(f"[ERR] Failed pages: {', '.join(ers)}")
        except Exception as e:
            self.log(f"[ERROR] Reset USER AREA failed: {e}")
            self.log_exception()
        finally:
            try:
                conn.disconnect()
            except Exception:
                pass

    # ---------- helpers for editor ----------
    def _group_pages(self, pages: dict[int, bytes]):
        """
        Group sparse page->bytes mapping into contiguous chunks for write_raw_pages.
        Each page must have exactly 4 bytes. Returns an iterator of (start_page, bytes).
        """
        items = sorted((int(p), bytes(v[:4]).ljust(4, b"\x00")) for p, v in pages.items())
        if not items:
            return []
        start = items[0][0]
        buf = bytearray(items[0][1])
        last = start
        out = []
        for p, b4 in items[1:]:
            if p == last + 1:
                buf.extend(b4)
            else:
                out.append((start, bytes(buf)))
                start = p
                buf = bytearray(b4)
            last = p
        out.append((start, bytes(buf)))
        return out

    # ---------- INI helpers ----------
    def _append_ini_line(self, sku: str, filament: str, color_name: str, color_hex: str) -> bool:
        return append_ini_line(sku, filament, color_name, color_hex, self._filament_ini_path)

    def _find_ini_record_for_base(self, base: str):
        if not base:
            return (None, None)
        candidates = [(k, v) for (k, v) in self.by_sku.items() if k.startswith(base + "-")]
        if not candidates:
            self.log(f"[DBG] _find_ini_record_for_base: no candidates for base '{base}'")
            return (None, None)
        cur_color = None
        if self.combo_color.currentIndex() > 0:
            cur_color = self.combo_color.currentText().strip()
        if cur_color:
            for k, v in candidates:
                if (v.color or "").strip() == cur_color:
                    return (k, v)
        return candidates[0]

    def _select_by_sku(self, sku_read: str) -> bool:
        base = sku_base(sku_read)
        if not base:
            self.log(f"[INFO] Keine gültige SKU-Basis für '{sku_read}' ermittelt.")
            return False
        sku_key, chosen = self._find_ini_record_for_base(base)
        if not chosen:
            self.log(f"[INFO] Keine Konfiguration für SKU-Basis '{base}' gefunden.")
            return False
        filament_name = chosen.filament
        idx_f = self.combo_filament.findText(filament_name, QtCore.Qt.MatchFixedString)
        if idx_f <= 0:
            self.log(f"[INFO] Filament '{filament_name}' nicht in Liste gefunden.")
            return False
        self.combo_filament.setCurrentIndex(idx_f)
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
        prev_filament = self.combo_filament.currentText() if self.combo_filament.currentIndex() > 0 else None
        prev_color = self.combo_color.currentText() if self.combo_color.currentIndex() > 0 else None
        try:
            self.by_filament, self.by_sku = load_filaments(None)
        except Exception as e:
            self.log(f"[ERROR] Reload filaments failed: {e}")
            self.log_exception()
            return
        self.combo_filament.blockSignals(True)
        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        names = sorted(self.by_filament.keys(), key=str.casefold)
        for name in names:
            self.combo_filament.addItem(name)
        self.combo_filament.blockSignals(False)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)
        self._set_color_indicator(None)
        if reseat_by_sku and getattr(self, "_last_read_full_sku", ""):
            if self._select_by_sku(self._last_read_full_sku):
                self._update_actions()
                return
        if prev_filament:
            idx_f = self.combo_filament.findText(prev_filament, QtCore.Qt.MatchFixedString)
            if idx_f > 0:
                self.combo_filament.setCurrentIndex(idx_f)
                if prev_color:
                    idx_c = self.combo_color.findText(prev_color, QtCore.Qt.MatchFixedString)
                    if idx_c > 0:
                        self.combo_color.setCurrentIndex(idx_c)
                        data = self.combo_color.currentData()
                        if data and len(data) >= 2:
                            self._set_color_indicator(data[1])
        self._update_actions()

    # ---------- reset selection ----------
    def on_reset_selection(self):
        self.combo_filament.blockSignals(True)
        self.combo_color.blockSignals(True)

        set_placeholder(self.combo_filament, PLACEHOLDER_FILAMENT)
        set_placeholder(self.combo_color, PLACEHOLDER_COLOR)
        self.combo_color.setEnabled(False)

        try:
            names = sorted(self.by_filament.keys(), key=str.casefold)
            for name in names:
                self.combo_filament.addItem(name)
        except Exception:
            pass

        self.combo_filament.blockSignals(False)
        self.combo_color.blockSignals(False)

        self._set_color_indicator(None)
        self._set_sku(None)
        self._last_read_full_sku = ""

        self._update_actions()
        self.log("[INFO] Selection reset.")

    # ---------- close ----------
    def closeEvent(self, event: QtGui.QCloseEvent):
        try:
            if hasattr(self, "_card_monitor") and hasattr(self, "_presence_observer"):
                try:
                    self._card_monitor.deleteObserver(self._presence_observer)
                except Exception:
                    pass
        finally:
            super().closeEvent(event)
