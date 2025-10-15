# tests/test_ndef_probe.py
import sys, binascii
from anycubic_nfc_qt5.nfc.pcsc import (
    list_readers, connect_first_reader, read_atr, read_uid,
    read_ndef_tlv, decode_ndef_records,
)

def fmt(b: bytes): 
    return " ".join(f"{x:02X}" for x in b)

def main():
    r = list_readers()
    if not r:
        print("[SKIP] No reader found. (macOS: brew install pcsc-lite && brew services start pcscd)")
        sys.exit(0)

    conn = connect_first_reader()
    if conn is None:
        print("[SKIP] No reader connection available.")
        sys.exit(0)

    try:
        conn.connect()
    except Exception:
        print("[SKIP] No card present. Place tag and retry.")
        sys.exit(0)

    atr = read_atr(conn) or b""
    print("[OK] ATR:", fmt(atr) if atr else "(empty)")
    uid, sw1, sw2 = read_uid(conn)
    if uid:
        print(f"[OK] UID: {fmt(uid)} (SW={sw1:02X}{sw2:02X})")
    else:
        print(f"[WARN] UID not available (SW={sw1:02X}{sw2:02X})")

    ndef = read_ndef_tlv(conn)
    if ndef:
        print(f"[OK] NDEF length: {len(ndef)} bytes")
        for rec in decode_ndef_records(ndef):
            print("[OK] NDEF:", rec)
        print("[HEX] NDEF raw:", binascii.hexlify(ndef).decode().upper())
    else:
        print("[INFO] No NDEF message found.")
    try:
        conn.disconnect()
    except Exception:
        pass

if __name__ == "__main__":
    main()