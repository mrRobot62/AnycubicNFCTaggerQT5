# tests/ntag_dump.py
# Dump Type-2 tag pages (NTAG/Ultralight family) via PC/SC (FF B0 00 <page> 04).
# - Reads a configurable page range and writes it to a binary file.
# - Prints a human-friendly view (HEX + ASCII) for each page.
# - Run while a tag is on the reader.

from __future__ import annotations
import sys
import argparse
from anycubic_nfc_qt5.nfc.pcsc import (
    list_readers,
    connect_first_reader,
    read_single_page,   # 4 bytes per page
)
from smartcard.Exceptions import NoCardException

def fmt_hex(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)

def fmt_ascii(b: bytes) -> str:
    return "".join(chr(x) if 32 <= x < 127 else "." for x in b)

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dump NTAG/Ultralight pages via PC/SC.")
    p.add_argument("--start", type=int, default=0, help="Start page (default: 0)")
    p.add_argument("--end",   type=int, default=47, help="End page inclusive (default: 47)")
    p.add_argument("--outfile", default="ntag_dump.bin", help="Output binary filename (default: ntag_dump.bin)")
    return p.parse_args()

def main():
    args = parse_args()

    if args.start < 0 or args.end < args.start:
        print("[ERROR] Invalid range. Ensure 0 <= start <= end.")
        sys.exit(1)

    readers = list_readers()
    if not readers:
        print("[ERROR] No PC/SC reader found.")
        sys.exit(1)

    conn = connect_first_reader()
    if conn is None:
        print("[ERROR] Failed to get connection object for first reader.")
        sys.exit(1)

    try:
        try:
            conn.connect()
        except NoCardException:
            print("[ERROR] No card present. Place a tag on the reader.")
            sys.exit(1)

        pages: list[bytes | None] = []
        for p in range(args.start, args.end + 1):
            try:
                data4 = read_single_page(conn, p)  # -> bytes(4)
            except Exception as e:
                print(f"{p:02d}: READ ERROR ({e})")
                data4 = None
            if data4 is None:
                print(f"{p:02d}: READ ERROR")
                pages.append(None)
            else:
                print(f"{p:02d}: {fmt_hex(data4)}   |{fmt_ascii(data4)}|")
                pages.append(data4)

        # Save binary (concatenate pages; missing pages become 00 00 00 00)
        out = bytearray()
        for b in pages:
            out.extend(b if b is not None else b"\x00\x00\x00\x00")
        with open(args.outfile, "wb") as f:
            f.write(out)

        print(f"\nSaved {len(out)} bytes to {args.outfile}")

    finally:
        try:
            conn.disconnect()
        except Exception:
            pass

if __name__ == "__main__":
    main()
    