# tests/test_anycubic_parse.py
# Probe-Tool für Anycubic-Tags (ohne GUI):
# - Verbindet zum ersten PC/SC-Reader
# - Liest ATR, UID
# - Liest Rohdaten-Felder (SKU, Brand, Material) und interpretiert bekannte Parameter
# - Gibt zusätzlich interessante Roh-Parameter aus
#
# Aufruf:
#   python tests/test_anycubic_parse.py
#
# Voraussetzungen:
#   - pyscard installiert
#   - PC/SC-Dienst läuft (macOS: brew install pcsc-lite && brew services start pcscd)
#   - Tag liegt auf dem Reader

from __future__ import annotations
import sys
from anycubic_nfc_qt5.nfc.pcsc import (
    list_readers,
    connect_first_reader,
    read_atr,
    read_uid,
    read_anycubic_fields,
    interpret_anycubic,
)

def _fmt_hex(b: bytes) -> str:
    """Format bytes as spaced uppercase hex."""
    return " ".join(f"{x:02X}" for x in b) if b else "(leer)"

def main() -> int:
    # Check reader availability
    readers = list_readers()
    if not readers:
        print("[SKIP] Kein PC/SC-Reader gefunden. (macOS: brew install pcsc-lite && brew services start pcscd)")
        return 0

    conn = connect_first_reader()
    if conn is None:
        print("[SKIP] Konnte keine Verbindung zum ersten Reader herstellen.")
        return 0

    # Try to connect to a card/tag
    try:
        conn.connect()  # will fail if no card is present
    except Exception:
        print("[SKIP] Keine Karte erkannt. Bitte Tag auflegen und erneut ausführen.")
        return 0

    # --- Low-level: ATR & UID ---
    atr = read_atr(conn) or b""
    print("[OK] ATR:", _fmt_hex(atr))

    uid, sw1, sw2 = read_uid(conn)
    if uid is not None:
        print(f"[OK] UID: {_fmt_hex(uid)} (SW={sw1:02X}{sw2:02X})")
    else:
        print(f"[WARN] UID konnte nicht gelesen werden (SW={sw1:02X}{sw2:02X}).")

    # --- Anycubic raw parse ---
    info = read_anycubic_fields(conn)
    nice = interpret_anycubic(info)

    sku = info.get("sku") or ""
    brand = info.get("brand") or ""
    material = info.get("material") or ""

    if sku:
        print("[OK] SKU:", sku)
    else:
        print("[INFO] SKU: (nicht gefunden)")
    print("[OK] Brand:", brand if brand else "(leer)")
    print("[OK] Material:", material if material else "(leer)")

    # Friendly/interpreted fields
    fr = nice.get("friendly", {})

    # Known mappings (from our current understanding)
    if "filament_diameter_mm" in fr:
        print(f"[OK] Filament Ø: {fr['filament_diameter_mm']:.2f} mm")

    if "nozzle_temp_min_c" in fr and "nozzle_temp_max_c" in fr:
        print(f"[OK] Nozzle-Temp: {fr['nozzle_temp_min_c']}–{fr['nozzle_temp_max_c']} °C")

    if "bed_temp_min_c" in fr and "bed_temp_max_c" in fr:
        print(f"[OK] Bed-Temp: {fr['bed_temp_min_c']}–{fr['bed_temp_max_c']} °C")

    if "spool_weight_g" in fr and "spool_weight_kg" in fr:
        print(f"[OK] Spulen-Gewicht: {fr['spool_weight_g']} g ({fr['spool_weight_kg']:.3f} kg)")

    # Unknown but interesting fields – keep visible for further reverse-engineering
    if "unknown_p30_b" in fr:
        print(f"[DBG] p30_b (unbekannt): {fr['unknown_p30_b']}")

    # Raw params block (useful to compare between tags/materials)
    params = info.get("params", {})
    if params:
        print("[DBG] Roh-Parameter (u16, little-endian):")
        for key in sorted(params.keys()):
            print(f"  - {key}: {params[key]}")

    # Optional: debug pages we cached in read_anycubic_fields
    for k in ("p20_raw", "p40_raw", "p41_raw", "p42_raw"):
        v = info.get(k)
        if isinstance(v, (bytes, bytearray)) and len(v) == 4:
            print(f"[DBG] {k}: {_fmt_hex(v)}")

    # Clean disconnect
    try:
        conn.disconnect()
    except Exception:
        pass

    return 0

if __name__ == "__main__":
    sys.exit(main())