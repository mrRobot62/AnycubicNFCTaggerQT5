# src/anycubic_nfc_qt5/config/ini_utils.py
from pathlib import Path
from . .utils.colors import normalize_hex_full

def update_color_for_sku(sku: str, new_hex: str, file_path: Path) -> bool:
    """
    Update the color hex for a given full SKU in ac_filaments.ini.
    Returns True on success, False on failure.
    """
    try:
        ini_path = file_path
        text = ini_path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        changed = False
        new_hex_full = normalize_hex_full(new_hex)

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

def append_ini_line(sku: str, filament: str, color_name: str, color_hex: str, file_path: Path) -> bool:
    """
    Append a new line to ac_filaments.ini in the form:
    SKU;FILAMENT;COLOR;#RRGGBBAA
    Returns True on success, False on failure.
    """
    try:
        ini_path = file_path
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
            return False

        new_line = f"{sku};{filament};{color_name};{color_hex}"

        # ensure trailing newline semantics
        txt = ini_path.read_text(encoding="utf-8", errors="ignore") if ini_path.exists() else ""
        with open(ini_path, "a", encoding="utf-8") as f:
            f.write(("" if txt.endswith("\n") or txt == "" else "\n") + new_line + "\n")

        return True
    except Exception:
        return False