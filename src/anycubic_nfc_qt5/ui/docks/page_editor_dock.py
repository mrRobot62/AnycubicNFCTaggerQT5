# src/anycubic_nfc_qt5/ui/docks/page_editor_dock.py
from __future__ import annotations

from typing import Dict, Iterable, Union, Optional
from PyQt5 import QtWidgets, QtCore, QtGui

# Try to import shared page metadata (nice to have, not strictly required)
try:
    from anycubic_nfc_qt5.ui.nfc_fields import PageSpan, PAGE_NAME_MAP  # type: ignore
except Exception:
    PageSpan = None  # duck-typing fallback later
    PAGE_NAME_MAP = {}  # no friendly names available


# ----------------------------- Validators & helpers -----------------------------

# Qt-style regex (QRegExp) validators
HEX_BYTE_QRE = QtCore.QRegExp(r"^(?:0x)?[0-9A-Fa-f]{0,2}$")  # single hex byte (0..2 hex digits), optional 0x
HEX_STREAM_QRE = QtCore.QRegExp(r"^\s*(?:0x)?[0-9A-Fa-f]{2}(?:\s+(?:0x)?[0-9A-Fa-f]{2})*\s*$")  # "AA 0xBB CC"

def _to_hex2(b: int) -> str:
    return f"{b & 0xFF:02X}"

def _bytes_to_ascii_4(b: bytes) -> str:
    """Return printable ASCII representation for 4 bytes (non-printables omitted)."""
    b = (b or b"")[:4]
    try:
        s = b.decode("ascii", errors="ignore")
    except Exception:
        s = ""
    return "".join(ch if 32 <= ord(ch) <= 126 else "" for ch in s)

def _ascii_to_4_bytes(s: str) -> bytes:
    b = (s or "").encode("ascii", errors="ignore")[:4]
    if len(b) < 4:
        b = b + b"\x00" * (4 - len(b))
    return b

def _hexstr_to_rgba_bytes(text: str) -> Optional[bytes]:
    """
    Parse '#RRGGBB' or '#RRGGBBAA' (case-insensitive) into RGBA (4 bytes).
    Returns None if format is invalid.
    """
    if not text:
        return None
    t = text.strip()
    if t.startswith("#"):
        t = t[1:]
    t = t.replace(" ", "").upper()
    if len(t) not in (6, 8):
        return None
    try:
        r = int(t[0:2], 16)
        g = int(t[2:4], 16)
        b = int(t[4:6], 16)
        a = int(t[6:8], 16) if len(t) == 8 else 0xFF
        return bytes((r, g, b, a))
    except Exception:
        return None

def _rgba_bytes_to_hex(b4: bytes) -> str:
    """Return '#RRGGBBAA' from 4 bytes."""
    b4 = (b4 or b"\x00\x00\x00\xFF")[:4].ljust(4, b"\x00")
    r, g, b, a = b4
    return f"#{r:02X}{g:02X}{b:02X}{a:02X}"


# ----------------------------- Editor row -----------------------------

class _Row(QtCore.QObject):
    """
    One editable row: [✓] 0xPP (dec) | Name | B0 B1 B2 B3 | ASCII(4)
    - Synchronizes HEX <-> ASCII.
    - For the configured "color" page it shows the ASCII cell as '#RRGGBBAA' and accepts it.
    """
    changed = QtCore.pyqtSignal(int, bytes)   # page, bytes(4)

    def __init__(self, page: int, parent: QtWidgets.QWidget, *, color_pretty: bool = False):
        super().__init__(parent)
        self.page = page
        self._color_pretty = color_pretty

        self.chkApply = QtWidgets.QCheckBox()
        self.lblPage = QtWidgets.QLabel(f"0x{page:02X}  ({page})")
        self.lblName = QtWidgets.QLabel(PAGE_NAME_MAP.get(page, "Unknown"))
        self.lblName.setStyleSheet("color:#666;")

        # four hex byte fields
        self.edB = []
        for _ in range(4):
            ed = QtWidgets.QLineEdit()
            ed.setMaxLength(2)
            ed.setFixedWidth(44)
            ed.setAlignment(QtCore.Qt.AlignCenter)
            ed.setPlaceholderText("00")
            ed.setValidator(QtGui.QRegExpValidator(HEX_BYTE_QRE, ed))
            self.edB.append(ed)

        # ASCII(4) field (or '#RRGGBBAA' on color row)
        self.edAscii = QtWidgets.QLineEdit()
        self.edAscii.setMaxLength(9 if color_pretty else 4)  # '#RRGGBBAA' => 9 chars
        self.edAscii.setFixedWidth(110 if color_pretty else 90)
        self.edAscii.setPlaceholderText("#RRGGBBAA" if color_pretty else "ASCII")

        # wiring
        for ed in self.edB:
            ed.textEdited.connect(self._on_hex_edited)
        self.edAscii.textEdited.connect(self._on_ascii_edited)

    # --- widgets access for layout ---
    def widgets(self):
        return (self.chkApply, self.lblPage, self.lblName, *self.edB, self.edAscii)

    # --- value accessors ---
    def get_bytes4(self) -> bytes:
        """Return exactly 4 bytes from hex inputs (empty -> 0x00)."""
        out = bytearray()
        for ed in self.edB:
            t = (ed.text() or "").strip()
            if not t:
                t = "00"
            if t.lower().startswith("0x"):
                t = t[2:]
            try:
                out.append(int(t, 16))
            except Exception:
                out.append(0)
        while len(out) < 4:
            out.append(0)
        return bytes(out[:4])

    def value(self) -> bytes:
        return self.get_bytes4()

    def set_value(self, b4: bytes, mark_changed: bool = False):
        """Set 4 bytes into hex and ASCII editors."""
        b4 = (b4 or b"\x00\x00\x00\x00")[:4].ljust(4, b"\x00")
        # hex
        for ed, val in zip(self.edB, b4):
            ed.blockSignals(True)
            ed.setText(_to_hex2(val))
            ed.blockSignals(False)
        # ascii
        self.edAscii.blockSignals(True)
        if self._color_pretty:
            self.edAscii.setText(_rgba_bytes_to_hex(b4))
        else:
            self.edAscii.setText(_bytes_to_ascii_4(b4))
        self.edAscii.blockSignals(False)

        if mark_changed:
            self.chkApply.setChecked(True)
        self.changed.emit(self.page, bytes(b4))

    def clear(self):
        for ed in self.edB:
            ed.blockSignals(True)
            ed.clear()
            ed.blockSignals(False)
        self.edAscii.blockSignals(True)
        self.edAscii.clear()
        self.edAscii.blockSignals(False)
        self.chkApply.setChecked(False)
        self.changed.emit(self.page, self.get_bytes4())

    # --- sync handlers ---
    def _on_hex_edited(self, _):
        b4 = self.get_bytes4()
        self.edAscii.blockSignals(True)
        if self._color_pretty:
            self.edAscii.setText(_rgba_bytes_to_hex(b4))
        else:
            self.edAscii.setText(_bytes_to_ascii_4(b4))
        self.edAscii.blockSignals(False)
        self.chkApply.setChecked(True)
        self.changed.emit(self.page, b4)

    def _on_ascii_edited(self, s: str):
        if self._color_pretty:
            rgba = _hexstr_to_rgba_bytes(s)
            if rgba is None:
                # fallback: treat as ASCII(4)
                b4 = _ascii_to_4_bytes(s)
            else:
                b4 = rgba
        else:
            b4 = _ascii_to_4_bytes(s)

        # push back into hex
        for ed, val in zip(self.edB, b4):
            ed.blockSignals(True)
            ed.setText(_to_hex2(val))
            ed.blockSignals(False)

        self.chkApply.setChecked(True)
        self.changed.emit(self.page, bytes(b4))


# ----------------------------- Dock widget -----------------------------

class PageEditorDock(QtWidgets.QDockWidget):
    """
    Scrollable page editor:
      - One row per page: [✓] 0xPP (dec) | Name | B0 B1 B2 B3 | ASCII(4/#RRGGBBAA)
      - Buttons: WRITE NFC, SIMULATE, CLEAR, DELETE (user area)
      - Prefill API accepts both int pages and PageSpan keys (bytes are chunked 4B/page)
    """

    # signals to MainWindow
    simulateRequested = QtCore.pyqtSignal(dict)            # {"pages": {page:int -> bytes(4)}}
    writePagesRequested = QtCore.pyqtSignal(dict)          # {"pages": {page:int -> bytes(4)}}
    deleteUserAreaRequested = QtCore.pyqtSignal()          # no payload
    clearUiRequested = QtCore.pyqtSignal()                 # request main to clear combos too

    def __init__(self, parent=None, max_page: int = 63, color_page: int = 0x20):
        super().__init__("Page Editor", parent)
        self.setObjectName("PageEditorDock")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable | QtWidgets.QDockWidget.DockWidgetMovable)

        self._max_page = int(max_page)
        self._color_page = int(color_page)
        self._rows: Dict[int, _Row] = {}

        # --- top buttons ---
        top = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(top)
        h.setContentsMargins(8, 8, 8, 8)
        self.btnWrite = QtWidgets.QPushButton("WRITE NFC")
        self.btnSim = QtWidgets.QPushButton("SIMULATE")
        self.btnClear = QtWidgets.QPushButton("CLEAR")
        self.btnDelete = QtWidgets.QPushButton("DELETE (User Area)")
        self.btnDelete.setStyleSheet("color:#a00;")
        h.addWidget(self.btnWrite)
        h.addStretch()
        h.addWidget(self.btnSim)
        h.addStretch()
        h.addWidget(self.btnClear)
        h.addWidget(self.btnDelete)

        # --- table header ---
        header = QtWidgets.QWidget()
        hh = QtWidgets.QGridLayout(header)
        hh.setContentsMargins(10, 0, 10, 0)
        hh.setColumnStretch(5, 1)
        hh.addWidget(QtWidgets.QLabel("Apply"), 0, 0)
        hh.addWidget(QtWidgets.QLabel("Page"), 0, 1)
        hh.addWidget(QtWidgets.QLabel("Name"), 0, 2)
        hh.addWidget(QtWidgets.QLabel("B0"), 0, 3)
        hh.addWidget(QtWidgets.QLabel("B1"), 0, 4)
        hh.addWidget(QtWidgets.QLabel("B2"), 0, 5)
        hh.addWidget(QtWidgets.QLabel("B3"), 0, 6)
        hh.addWidget(QtWidgets.QLabel("ASCII"), 0, 7)

        # --- rows (scroll area) ---
        body = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(body)
        grid.setContentsMargins(10, 0, 10, 10)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        for p in range(self._max_page + 1):
            row = _Row(p, body, color_pretty=(p == self._color_page))
            self._rows[p] = row
            (chk, lpg, lname, b0, b1, b2, b3, asc) = row.widgets()
            r = p + 1  # row 0 is header
            grid.addWidget(chk,   r, 0)
            grid.addWidget(lpg,   r, 1)
            grid.addWidget(lname, r, 2)
            grid.addWidget(b0,    r, 3)
            grid.addWidget(b1,    r, 4)
            grid.addWidget(b2,    r, 5)
            grid.addWidget(b3,    r, 6)
            grid.addWidget(asc,   r, 7)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)

        # --- root layout ---
        cont = QtWidgets.QWidget(self)
        v = QtWidgets.QVBoxLayout(cont)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(top)
        v.addWidget(header)
        v.addWidget(scroll)

        self.setWidget(cont)

        # signals
        self.btnWrite.clicked.connect(self._on_write)
        self.btnSim.clicked.connect(self._on_sim)
        self.btnClear.clicked.connect(self._on_clear)
        self.btnDelete.clicked.connect(self._on_delete)

    # ---------------- public API ----------------

    def stage_pages(self, pages_to_bytes: Dict[Union[int, object], bytes], mark_changed: bool = False):
        """
        Accepts either:
          - {page:int -> bytes}      (bytes length may be >4; will be chunked across consecutive pages)
          - {span:PageSpan -> bytes} (will be chunked across span.iter_pages())
        Each page gets exactly 4 bytes (padded with zeros).
        """
        if not pages_to_bytes:
            return

        def is_pagespan(obj) -> bool:
            # strict type if available
            if PageSpan is not None and isinstance(obj, PageSpan):  # type: ignore
                return True
            # duck-typing fallback
            return hasattr(obj, "iter_pages") and hasattr(obj, "start") and hasattr(obj, "pages")

        for key, payload in pages_to_bytes.items():
            data = bytes(payload or b"")
            if is_pagespan(key):
                # distribute across span pages
                pages = list(key.iter_pages())  # type: ignore[attr-defined]
                off = 0
                for p in pages:
                    if off >= len(data):
                        break
                    chunk = data[off: off + 4]
                    if len(chunk) < 4:
                        chunk = chunk + b"\x00" * (4 - len(chunk))
                    row = self._rows.get(int(p))
                    if row:
                        row.set_value(chunk, mark_changed=mark_changed)
                    off += 4
            else:
                # treat as single starting page
                try:
                    start = int(key)
                except Exception:
                    # unknown key type; skip gracefully
                    continue
                off = 0
                p = start
                while off < len(data):
                    chunk = data[off: off + 4]
                    if len(chunk) < 4:
                        chunk = chunk + b"\x00" * (4 - len(chunk))
                    row = self._rows.get(p)
                    if row:
                        row.set_value(chunk, mark_changed=mark_changed)
                    off += 4
                    p += 1

    def clear_all_rows(self):
        for row in self._rows.values():
            row.clear()

    def gather_selected_pages(self) -> Dict[int, bytes]:
        """
        Collect pages marked with 'Apply' checkbox.
        Returns {page:int -> bytes(4)} in ascending order.
        """
        out: Dict[int, bytes] = {}
        for p in sorted(self._rows.keys()):
            row = self._rows[p]
            if row.chkApply.isChecked():
                out[p] = row.value()
        return out

    # Convenience prefill helpers (optional to use from MainWindow)
    def stage_prefill_bytes_range(self, start_page: int, payload: bytes, *, override: bool = False, max_pages: Optional[int] = None):
        """
        Prefill a byte stream starting at 'start_page' across consecutive pages (4 bytes/page).
        If override=False, only pages currently equal to 00 00 00 00 will be filled.
        """
        if not payload:
            return
        data = bytes(payload)
        if max_pages is not None:
            data = data[: max_pages * 4]
        off = 0
        p = int(start_page)
        while off < len(data) and p in self._rows:
            chunk = data[off: off + 4]
            if len(chunk) < 4:
                chunk = chunk + b"\x00" * (4 - len(chunk))
            row = self._rows[p]
            cur = row.get_bytes4()
            if override or not any(cur):
                row.set_value(chunk, mark_changed=False)
            off += 4
            p += 1

    def stage_prefill_ascii_range(self, start_page: int, text: str, *, override: bool = False, max_pages: Optional[int] = None):
        """Prefill ASCII text starting at 'start_page' across pages."""
        data = (text or "").encode("ascii", errors="ignore")
        self.stage_prefill_bytes_range(start_page, data, override=override, max_pages=max_pages)

    # ---------------- buttons ----------------

    def _on_write(self):
        payload = {"pages": self.gather_selected_pages()}
        if not payload["pages"]:
            QtWidgets.QMessageBox.information(self, "Nothing to write", "No rows marked with 'Apply'.")
            return
        self.writePagesRequested.emit(payload)

    def _on_sim(self):
        payload = {"pages": self.gather_selected_pages()}
        if not payload["pages"]:
            QtWidgets.QMessageBox.information(self, "Nothing to simulate", "No rows marked with 'Apply'.")
            return
        self.simulateRequested.emit(payload)

    def _on_clear(self):
        ans = QtWidgets.QMessageBox.question(
            self, "Clear editor",
            "Clear all inputs in the editor and also clear filament/color selection?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if ans == QtWidgets.QMessageBox.Yes:
            self.clear_all_rows()
            self.clearUiRequested.emit()

    def _on_delete(self):
        txt, ok = QtWidgets.QInputDialog.getText(
            self, "Delete user area",
            "Type 'RESET' to clear the user area on the tag:"
        )
        if ok and txt.strip().upper() == "RESET":
            self.deleteUserAreaRequested.emit()