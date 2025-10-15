# src/anycubic_nfc_qt5/config/filaments.py
from __future__ import annotations
import csv
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from importlib import resources

@dataclass(frozen=True)
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