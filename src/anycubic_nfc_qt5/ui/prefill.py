# src/anycubic_nfc_qt5/ui/prefill.py
"""
Helpers to create page->bytes mappings for the PageEditorDock.
Keeps main_window.py slimmer.
"""

from __future__ import annotations


def color_hex_to_rgba4(hex_full: str) -> bytes:
    """
    Convert '#RRGGBB' or '#RRGGBBAA' to 4 bytes RGBA.
    Missing alpha is filled with 0xFF.
    """
    s = (hex_full or "").strip().lstrip("#").upper()
    if len(s) == 6:
        s += "FF"
    while len(s) < 8:
        s += "0"
    return bytes(int(s[i:i + 2], 16) for i in range(0, 8, 2))


def map_ascii_to_pages(start_page: int, text: str, *, max_pages: int | None = None) -> dict[int, bytes]:
    """
    Map ASCII text to consecutive pages starting at 'start_page'.
    Each page holds 4 bytes. The last chunk is padded with 0x00.
    Returns a dict {page_index: 4-bytes}.
    """
    data = (text or "").encode("ascii", errors="ignore")
    pages: dict[int, bytes] = {}
    if max_pages is not None:
        data = data[: max_pages * 4]
    p = start_page
    off = 0
    while off < len(data):
        chunk = data[off: off + 4]
        if len(chunk) < 4:
            chunk = chunk + b"\x00" * (4 - len(chunk))
        pages[p] = chunk
        p += 1
        off += 4
    # Ensure at least one page when text is empty (useful for vendor/material placeholders)
    if not pages and max_pages and max_pages > 0:
        pages[start_page] = b"\x00\x00\x00\x00"
    return pages