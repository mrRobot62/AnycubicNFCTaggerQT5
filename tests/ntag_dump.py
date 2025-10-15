# tests/ntag_dump.py
# Dump Type-2 tag pages (NTAG/Ultralight family) via PC/SC (FF B0 00 <page> 04).
# - Reads pages 0..47 (48 pages), saves binary to ntag_dump.bin and prints a human view.
# - Run while a tag is on the reader.

from __future__ import annotations
import sys
import binascii
from anycubic_nfc_qt5.nfc.pcsc import list_readers, connect_first_reader, read_page_ultralight

def fmt_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

def fmt_ascii(b: bytes) -> str:
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b)

def main():
    r = list_readers()
    if not r:
        print("[ERROR] No PC/SC reader found.")
        sys.exit(1)

    conn = connect_first_reader()
    if conn is None:
        print("[ERROR] Failed to get connection object for first reader.")
        sys.exit(1)

    try:
        conn.connect()
    except Exception as e:
        print("[ERROR] No card present or connect failed:", e)
        sys.exit(1)

    pages = []
    MAX_PAGE = 47  # read pages 0..47 (adjust if needed)
    for p in range(0, MAX_PAGE + 1):
        b = read_page_ultralight(conn, p)
        if b is None:
            print(f"{p:02d}: READ ERROR")
            # stop on read error or continue? we continue to show what we have
            pages.append(None)
        else:
            pages.append(b)
            print(f"{p:02d}: {fmt_hex(b)}   |{fmt_ascii(b)}|")

    # save binary (concatenate all readable pages)
    out = bytearray()
    for b in pages:
        if b is None:
            out.extend(b"\x00\x00\x00\x00")  # placeholder
        else:
            out.extend(b)
    fn = "ntag_dump.bin"
    with open(fn, "wb") as f:
        f.write(out)
    print(f"\nSaved {len(out)} bytes to {fn}")

    try:
        conn.disconnect()
    except Exception:
        pass

if __name__ == "__main__":
    main()