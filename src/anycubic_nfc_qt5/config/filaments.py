# src/anycubic_nfc_qt5/config/filaments.py
from __future__ import annotations
import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from importlib import resources
from pathlib import Path

@dataclass(frozen=False)    # False=change properties is possible, True=this class is readonly
class FilamentRecord:
    sku: str
    filament: str
    color: str
    color_hex: str

def _open_filament_file(path: Optional[str]):
    if path:
        return open(path, "r", encoding="utf-8")
    # packaged default
    return (resources.files(__package__).joinpath("ac_filaments.ini")
            .open("r", encoding="utf-8"))

def load_filaments(path: Optional[str] = None) -> Tuple[Dict[str, List[FilamentRecord]], Dict[str, FilamentRecord]]:
    """
    Returns:
      - by_filament: { FILAMENT: [FilamentRecord, ...] }
      - by_sku:      { SKU: FilamentRecord }
    """
    by_filament: Dict[str, List[FilamentRecord]] = {}
    by_sku: Dict[str, FilamentRecord] = {}

    with _open_filament_file(path) as f:
        # ignore empty lines / comments
        def non_comment_lines():
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                yield line

        reader = csv.reader(non_comment_lines(), delimiter=";")
        # header optional
        first = next(reader, None)
        rows = []
        if first is None:
            return by_filament, by_sku
        if first and first[0].strip().upper() == "SKU":
            rows = list(reader)
        else:
            rows = [first] + list(reader)

        for row in rows:
            # tolerate short rows
            parts = [c.strip() for c in row] + ["", "", "", ""]
            sku, filament, color, color_hex = parts[0], parts[1], parts[2], parts[3]
            if not sku or not filament:
                continue
            rec = FilamentRecord(sku=sku, filament=filament, color=color, color_hex=color_hex or "#000000FF")
            by_sku[sku] = rec
            by_filament.setdefault(filament, []).append(rec)

    return by_filament, by_sku


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
            # tolerate spaces/tabs; compare by first field before ';'
            parts = [p.strip() for p in ln.split(";")]
            if not parts or parts[0] != sku:
                out_lines.append(ln)
                continue
            # ensure at least 4 fields: SKU;FILAMENT;COLOR;COLOR_HEX
            while len(parts) < 4:
                parts.append("")
            parts[3] = new_hex_full
            out_lines.append(";".join(parts))
            changed = True

        if not changed:
            return False  # sku not found

        ini_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False