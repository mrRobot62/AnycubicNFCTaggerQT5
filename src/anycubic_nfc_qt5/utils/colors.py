# src/anycubic_nfc_qt5/utils/colors.py
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

def normalize_hex_full(h: str) -> str:
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