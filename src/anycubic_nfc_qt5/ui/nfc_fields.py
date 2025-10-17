# src/anycubic_nfc_qt5/ui/nfc_fields.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List


# ---------- Models ----------

@dataclass(frozen=True)
class PageSpan:
    """
    A consecutive run of pages on a Type-2 tag (4 bytes per page).

    Attributes
    ---------
    start : int
        First page index (inclusive).
    pages : int
        Number of pages in the span.

    Derived
    -------
    end : int
        Last page index (inclusive).

    Methods
    -------
    iter_pages() -> Iterable[int]
        Iterate page indices in this span.
    """
    start: int
    pages: int

    @property
    def end(self) -> int:
        return self.start + self.pages - 1

    def iter_pages(self) -> Iterable[int]:
        return range(self.start, self.start + self.pages)


class P:
    """
    Central mapping of logical Anycubic fields to page spans.
    Adjust these to match your tag layout.

    NOTE: All higher-level code (UI, read/write, prefill) should import and use
    these spans through the mapper helpers below (map_ascii_span, map_u16, ...).
    """
    # Long ASCII fields (based on your dump/observations)
    SKU           = PageSpan(0x05, 5)   # 5 pages = 20 bytes (e.g., "HTPCP-101")
    MATERIAL      = PageSpan(0x15, 8)   # 8 pages = 32 bytes ("TPU Filament..." etc.)
    MANUFACTURER  = PageSpan(0x10, 1)   # 1 page = 4 bytes ASCII ("AC")
    VENDOR        = MANUFACTURER        # optional alias if legacy code uses VENDOR

    # Color (RGBA on a single page)
    COLOR         = PageSpan(0x20, 1)   # store as RGBA: R,G,B,A (4 bytes)

    # Numeric fields (U16 per page; little-endian by default here)
    DIAMETER_CENTI = PageSpan(0x11, 1)  # 1.75 mm -> 175 (centi-mm)
    NOZZLE_MIN      = PageSpan(0x12, 1)
    NOZZLE_MAX      = PageSpan(0x13, 1)
    BED_MIN         = PageSpan(0x14, 1)
    BED_MAX         = PageSpan(0x18, 1)

    # Ranges (A/B/C) — set if/when you confirm them
    RANGE_A         = PageSpan(0x21, 1)
    RANGE_B         = PageSpan(0x22, 1)
    RANGE_C         = PageSpan(0x23, 1)

    # Filament type, if used separately from MATERIAL
    TYPE            = PageSpan(0x17, 1)

    # Confirmed: filament weight is on page 0x31
    WEIGHT_G        = PageSpan(0x31, 1)


# ---------- Human-friendly page names ----------

PAGE_NAME_MAP: Dict[int, str] = {
    # Core fields
    0x05: "SKU (part 1)",              # rest of SKU is covered by the span
    0x10: "Manufacturer / Vendor",
    0x15: "Material",
    0x20: "Color (RGBA)",

    # Filament data
    0x11: "Filament Diameter (centi-mm)",
    0x17: "Filament Type",
    0x31: "Filament Weight (g)",

    # Temperatures
    0x12: "NozzleTemp Min (°C)",
    0x13: "NozzleTemp Max (°C)",
    0x14: "BedTemp Min (°C)",
    0x18: "BedTemp Max (°C)",

    # Ranges (optional / TBD)
    0x21: "Range A",
    0x22: "Range B",
    0x23: "Range C",
}


def page_name_for(page: int) -> str:
    """
    Return a human-friendly name for a page if known; otherwise 'Unknown'.
    """
    return PAGE_NAME_MAP.get(int(page), "Unknown")


# ---------- Mapping helpers (build {page:int -> bytes(4)}) ----------

def to_rgba_bytes(hex_full: str) -> bytes:
    """
    Convert '#RRGGBB' or '#RRGGBBAA' to 4 bytes RGBA.
    If alpha is missing, default to 0xFF.

    Examples
    --------
    '#800080'    -> 80 00 80 FF
    '#800080CC'  -> 80 00 80 CC
    """
    s = (hex_full or "").strip().lstrip("#").upper()
    if len(s) == 0:
        return b"\x00\x00\x00\xFF"
    if len(s) == 6:
        s += "FF"
    while len(s) < 8:
        s += "0"
    return bytes(int(s[i:i+2], 16) for i in range(0, 8, 2))


def _chunk4(data: bytes, max_pages: int | None = None) -> List[bytes]:
    """
    Yield 4-byte chunks from data. Pads the final chunk with zeros.
    Optionally truncates to max_pages*4 bytes.

    NOTE: This function returns at least one chunk *only* if data is non-empty.
    """
    if not data:
        return []
    if max_pages is not None:
        data = data[: max_pages * 4]
    out: List[bytes] = []
    off = 0
    n = len(data)
    while off < n:
        chunk = data[off:off+4]
        if len(chunk) < 4:
            chunk = chunk + b"\x00" * (4 - len(chunk))
        out.append(chunk)
        off += 4
    return out


def map_ascii_span(span: PageSpan, text: str, *, max_pages: int | None = None) -> Dict[int, bytes]:
    """
    Map an ASCII string across a span of pages (4 bytes per page).
    Returns {page: bytes(4), ...}.

    IMPORTANT: If 'text' is empty/None, returns {} (no destructive zero-prefill).
    """
    if not text:
        return {}
    raw = (text or "").encode("ascii", errors="ignore")
    pages = list(span.iter_pages())
    chunks = _chunk4(raw, max_pages=max_pages)
    mapping: Dict[int, bytes] = {}
    for i, p in enumerate(pages):
        if i >= len(chunks):
            break
        mapping[p] = chunks[i]
    return mapping


def map_color_rgba(span_color: PageSpan, hex_full: str) -> Dict[int, bytes]:
    """
    Map a RGBA color to its single page. Expects span_color.pages == 1.
    """
    if span_color.pages <= 0:
        return {}
    return {span_color.start: to_rgba_bytes(hex_full)}


def map_u16(span: PageSpan, value: int, *, byteorder: str = "little") -> Dict[int, bytes]:
    """
    Map a 16-bit integer into a single page as: [lo, hi, 0x00, 0x00] (little-endian by default).
    Use byteorder='big' if your tag uses big-endian encoding.

    IMPORTANT: If value is None, returns {} (no write).
    """
    if span.pages <= 0 or value is None:
        return {}
    v = int(value) & 0xFFFF
    if byteorder == "big":
        b0 = (v >> 8) & 0xFF
        b1 = v & 0xFF
    else:
        b0 = v & 0xFF
        b1 = (v >> 8) & 0xFF
    return {span.start: bytes((b0, b1, 0x00, 0x00))}


# ---------- Convenience: list of numeric pages (optional) ----------

U16_PAGES: List[int] = [
    P.DIAMETER_CENTI.start,
    P.NOZZLE_MIN.start,
    P.NOZZLE_MAX.start,
    P.BED_MIN.start,
    P.BED_MAX.start,
    P.WEIGHT_G.start,
]