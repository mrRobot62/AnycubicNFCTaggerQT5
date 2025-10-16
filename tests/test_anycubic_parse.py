# tests/test_anycubic_parse.py
# Standalone probe tool for Anycubic NFC tags (no GUI).
# - Connects to first PC/SC reader
# - Reads ATR, UID
# - Parses Anycubic raw fields (SKU, manufacturer, material, color, ranges, temps, diameter, length, weight)
# - Prints human-friendly interpretation
#
# Usage:
#   python tests/test_anycubic_parse.py
#
# Requirements:
#   - pyscard installed
#   - PC/SC service running (macOS: brew install pcsc-lite && brew services start pcscd)
#   - Place the tag on the reader before running

from __future__ import annotations
import sys
from typing import Optional, Dict, Any

from anycubic_nfc_qt5.nfc.pcsc import (
    list_readers,
    connect_first_reader,
    read_atr,
    read_uid,
    read_anycubic_fields,   # expects parser you added in nfc/pcsc.py
    interpret_anycubic,     # expects interpreter you added in nfc/pcsc.py
)

def _fmt_hex(b: Optional[bytes]) -> str:
    """Format bytes as spaced uppercase hex."""
    if not b:
        return "(leer)"
    return " ".join(f"{x:02X}" for x in b)

def _print_header(title: str):
    print("\n" + title)
    print("-" * len(title))

def _print_ranges(ranges: Dict[str, Dict[str, Optional[int]]]):
    """Pretty-print ranges block: A/B/C with speed/nozzle min/max."""
    order = ("A", "B", "C")
    for key in order:
        r = ranges.get(key)
        if not r:
            continue
        smin = r.get("speed_min")
        smax = r.get("speed_max")
        nmin = r.get("nozzle_min")
        nmax = r.get("nozzle_max")
        def _fmt_pair(a, b, unit=""):
            if a is None or b is None:
                return "–"
            return f"{a}–{b}{unit}"
        print(f"[DBG] Range {key}: Speed={_fmt_pair(smin, smax)} | Nozzle={_fmt_pair(nmin, nmax, ' °C')}")

def main() -> int:
    # Check for readers
    readers = list_readers()
    if not readers:
        print("[SKIP] Kein PC/SC-Reader gefunden. (macOS: brew install pcsc-lite && brew services start pcscd)")
        return 0

    # Connect to first reader
    conn = connect_first_reader()
    if conn is None:
        print("[SKIP] Konnte keine Verbindung zum ersten Reader herstellen.")
        return 0

    # Try to connect to a tag/card
    try:
        conn.connect()  # raises if no tag present
    except Exception:
        print("[SKIP] Keine Karte erkannt. Bitte Tag auflegen und erneut ausführen.")
        return 0

    # --- Low-level identification ---
    _print_header("Identifikation")
    atr = read_atr(conn) or b""
    print("[OK] ATR:", _fmt_hex(atr))

    uid, sw1, sw2 = read_uid(conn)
    if uid is not None:
        print(f"[OK] UID: {_fmt_hex(uid)} (SW={sw1:02X}{sw2:02X})")
    else:
        print(f"[WARN] UID konnte nicht gelesen werden (SW={sw1:02X}{sw2:02X}).")

    # --- Anycubic parse + interpretation ---
    info: Dict[str, Any] = read_anycubic_fields(conn)
    nice: Dict[str, Any] = interpret_anycubic(info)
    fr: Dict[str, Any] = nice.get("friendly", {}) or {}

    _print_header("Basisdaten")
    sku = info.get("sku") or ""
    manufacturer = info.get("manufacturer") or ""
    material = info.get("material") or ""
    color_hex = info.get("color_hex") or ""

    print("[OK] p05:SKU:", sku if sku else "(nicht gefunden)")
    print("[OK] p10:Hersteller:", manufacturer if manufacturer else "(leer)")
    print("[OK] p15:Material:", material if material else "(leer)")
    print("[OK] p20:Farbe (HEX):", color_hex if color_hex else "(unbekannt)")

    # Friendly derived fields
    _print_header("Interpretation")
    if "p30_a:filament_diameter_mm" in fr:
        print(f"[OK] Filament Ø: {fr['filament_diameter_mm']:.2f} mm")
    if "speed_min" in fr and "speed_max" in fr:
        print(f"[OK] Speed-Range (aus A/B/C): {fr['speed_min']}–{fr['speed_max']}")
    if "p24_a/b:nozzle_temp_min_c" in fr and "nozzle_temp_max_c" in fr:
        print(f"[OK] Nozzle-Temp: {fr['nozzle_temp_min_c']}–{fr['nozzle_temp_max_c']} °C")
    # Bed temps
    if "p29_a/b:bed_temp_min_c" in fr and "bed_temp_max_c" in fr:
        print(f"[OK] Bed-Temp: {fr['bed_temp_min_c']}–{fr['bed_temp_max_c']} °C")
    # Length & weight (some are in info)
    if info.get("length_m") is not None:
        print(f"[OK] p30_b:Filament-Länge: {info['length_m']} m")
    if "p31:spool_weight_g" in fr and "spool_weight_kg" in fr:
        print(f"[OK] p31_a:Spulen-Gewicht: {fr['spool_weight_g']} g ({fr['spool_weight_kg']:.3f} kg)")
    # Unknown but interesting fields could be printed here if needed

    # Print all ranges (debug)
    rng = fr.get("ranges", {})
    if rng:
        _print_header("Ranges (A/B/C) – Debug")
        _print_ranges(rng)

    # Optional debug: show some raw pages we cached (if present)
    raw_keys = ("p20_raw", "p40_raw", "p41_raw", "p42_raw")
    dbg_present = any(isinstance(info.get(k), (bytes, bytearray)) for k in raw_keys)
    if dbg_present:
        _print_header("Roh-Bytes (Debug)")
        for k in raw_keys:
            v = info.get(k)
            if isinstance(v, (bytes, bytearray)) and len(v) == 4:
                print(f"[DBG] {k}: {_fmt_hex(v)}")

    # Clean disconnect
    try:
        conn.disconnect()
    except Exception:
        pass

    print("\n[FERTIG]")
    return 0

if __name__ == "__main__":
    sys.exit(main())