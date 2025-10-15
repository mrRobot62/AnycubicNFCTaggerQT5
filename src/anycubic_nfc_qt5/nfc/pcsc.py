# src/anycubic_nfc_qt5/nfc/pcsc.py
# Minimal PC/SC helpers for detecting readers, connecting, and reading ATR/UID.
from __future__ import annotations
import time
from typing import List, Optional, Tuple

from smartcard.System import readers
from smartcard.CardConnection import CardConnection


def list_readers() -> List:
    """Return available PC/SC readers."""
    try:
        return readers()
    except Exception:
        return []


def connect_first_reader() -> Optional[CardConnection]:
    """Create connection object to the first available reader (not yet connected)."""
    rlist = list_readers()
    if not rlist:
        return None
    return rlist[0].createConnection()


def wait_for_card(timeout_s: float = 30.0, poll_interval_s: float = 0.5) -> Optional[CardConnection]:
    """Poll the first reader until a card is present or timeout."""
    conn = connect_first_reader()
    if conn is None:
        return None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            conn.connect()  # will raise until a card is present
            return conn
        except Exception:
            time.sleep(poll_interval_s)
    return None


def read_atr(conn: CardConnection) -> bytes:
    """Return ATR bytes of the connected card (already connected)."""
    atr = conn.getATR()
    return bytes(atr) if atr else b""


def read_uid(conn: CardConnection) -> Tuple[Optional[bytes], int, int]:
    """
    Try to read card UID using a common APDU for ACR122/ACR125x:
    FF CA 00 00 00  -> returns UID, SW1, SW2
    Not all readers/cards support this. Handle gracefully.
    """
    try:
        cmd = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = conn.transmit(cmd)
        if sw1 == 0x90 and sw2 == 0x00:
            return bytes(data), sw1, sw2
        return None, sw1, sw2
    except Exception:
        return None, 0x6F, 0x00  # 6F00 = generic error
    
# --- Ultralight / NTAG helpers (PC/SC READ BINARY) ---
def read_page_ultralight(conn, page: int):
    """Read a single 4-byte page from Ultralight/NTAG using PC/SC READ BINARY.
    Returns 4 bytes on success, or None on failure."""
    try:
        # APDU: FF B0 00 <page> 04  -> read 4 bytes (one page)
        apdu = [0xFF, 0xB0, 0x00, page & 0xFF, 0x04]
        data, sw1, sw2 = conn.transmit(apdu)
        if sw1 == 0x90 and sw2 == 0x00:
            return bytes(data)
        return None
    except Exception:
        return None


def read_pages_ultralight(conn, start_page: int, page_count: int) -> bytes:
    """Read multiple 4-byte pages consecutively; returns concatenated bytes (best-effort)."""
    out = bytearray()
    for p in range(start_page, start_page + page_count):
        b = read_page_ultralight(conn, p)
        if b is None:
            break
        out.extend(b)
    return bytes(out)


def find_ndef_tlv(mem: bytes):
    """Scan a Type 2 Tag TLV area for NDEF TLV (0x03).
    Returns (offset_of_value, ndef_len, total_tlv_length) or (None, None, None) if not found.
    Supports short length (1 byte) and extended length (0xFF + 2 bytes)."""
    i = 0
    n = len(mem)
    while i < n:
        t = mem[i]
        if t == 0x00:  # NULL TLV
            i += 1
            continue
        if t == 0xFE:  # Terminator TLV
            break
        if i + 1 >= n:
            break
        l = mem[i + 1]
        if t == 0x03:  # NDEF Message TLV
            if l != 0xFF:
                value_off = i + 2
                ndef_len = l
                total = 2 + ndef_len
                if value_off + ndef_len <= n:
                    return value_off, ndef_len, total
                else:
                    return value_off, ndef_len, None
            else:
                # Extended length: next two bytes are length (big-endian)
                if i + 3 >= n:
                    break
                ndef_len = (mem[i + 2] << 8) | mem[i + 3]
                value_off = i + 4
                total = 4 + ndef_len
                if value_off + ndef_len <= n:
                    return value_off, ndef_len, total
                else:
                    return value_off, ndef_len, None
        else:
            # Skip non-NDEF TLV
            if l != 0xFF:
                skip_len = 2 + l
            else:
                if i + 3 >= n:
                    break
                skip_len = 4 + ((mem[i + 2] << 8) | mem[i + 3])
            i += skip_len
            continue
        i += 1
    return None, None, None


def read_ndef_tlv(conn, max_pages: int = 0x30):
    """Read NDEF message bytes from a Type 2 Tag (e.g., NTAG213/215/216).
    Starts at page 4 (user area start), scans TLVs for NDEF (0x03), then returns the NDEF payload bytes.
    max_pages is a soft cap to avoid excessive reads; defaults to 0x30 (48 pages).
    Returns None if not found or on error."""
    start_page = 4
    chunk_pages = 16  # 16 pages = 64 bytes
    collected = bytearray()
    pages_read = 0
    while pages_read < max_pages:
        to_read = min(chunk_pages, max_pages - pages_read)
        chunk = read_pages_ultralight(conn, start_page + pages_read, to_read)
        if not chunk:
            break
        collected.extend(chunk)
        off, nlen, total = find_ndef_tlv(collected)
        if off is not None and nlen is not None:
            end = off + nlen
            if end <= len(collected):
                return bytes(collected[off:end])
            # else: need more bytes → continue reading
        pages_read += to_read
    return None


# --- Minimal NDEF decode helpers (URI / Text) ---
def decode_ndef_records(ndef: bytes):
    """Very small NDEF decoder for common single-record messages (Text 'T', URI 'U').
    Returns a list of human-readable strings; falls back to hex if unrecognized."""
    out = []
    i = 0
    try:
        while i < len(ndef):
            hdr = ndef[i]; i += 1
            mb = (hdr & 0x80) != 0  # not used, but kept for completeness
            me = (hdr & 0x40) != 0
            sr = (hdr & 0x10) != 0
            tnf = hdr & 0x07

            if i >= len(ndef): break
            type_len = ndef[i]; i += 1

            if sr:
                if i >= len(ndef): break
                payload_len = ndef[i]; i += 1
            else:
                if i + 3 >= len(ndef): break
                payload_len = (ndef[i] << 24) | (ndef[i+1] << 16) | (ndef[i+2] << 8) | ndef[i+3]
                i += 4

            # no ID field support (IL=0 assumed)
            type_field = ndef[i:i+type_len]; i += type_len
            payload = ndef[i:i+payload_len]; i += payload_len

            if tnf == 0x01:  # Well-known
                if type_field == b'T' and payload:
                    # Text RTD
                    status = payload[0]
                    lang_len = status & 0x3F
                    utf16 = (status & 0x80) != 0
                    lang = payload[1:1+lang_len].decode('ascii', errors='ignore')
                    text = payload[1+lang_len:].decode('utf-16' if utf16 else 'utf-8', errors='replace')
                    out.append(f"Text('{text}', lang={lang})")
                elif type_field == b'U' and payload:
                    prefixes = [
                        "", "http://www.", "https://www.", "http://", "https://",
                        "tel:", "mailto:", "ftp://anonymous:anonymous@", "ftp://ftp.",
                        "ftps://", "sftp://", "smb://", "nfs://", "ftp://", "dav://",
                        "news:", "telnet://", "imap:", "rtsp://", "urn:", "pop:",
                        "sip:", "sips:", "tftp:", "btspp://", "btl2cap://", "btgoep://",
                        "tcpobex://", "irdaobex://", "file://", "urn:epc:id:", "urn:epc:tag:",
                        "urn:epc:pat:", "urn:epc:raw:", "urn:epc:", "urn:nfc:"
                    ]
                    code = payload[0]
                    uri = (prefixes[code] if code < len(prefixes) else "") + payload[1:].decode('utf-8', errors='replace')
                    out.append(f"URI('{uri}')")
                else:
                    out.append(f"WellKnown(type={type_field!r}, {len(payload)} bytes)")
            else:
                out.append(f"TNF={tnf}, type={type_field!r}, {len(payload)} bytes")

            # continue in case of multiple records; ME flag indicates end of message
            if me:
                pass

        if not out:
            out.append(f"Raw NDEF ({len(ndef)} bytes)")
    except Exception:
        out.append(f"Raw NDEF ({len(ndef)} bytes)")
    return out

# --- Anycubic raw page parsing (experimental) ---
def _read_ascii_z(conn, start_page: int, max_len: int = 32) -> str:
    """Read a zero-terminated ASCII string from pages starting at start_page."""
    buf = bytearray()
    p = start_page
    while len(buf) < max_len:
        b = read_page_ultralight(conn, p)
        if b is None:
            break
        buf.extend(b)
        if 0x00 in b:
            break
        p += 1
    s = bytes(buf).split(b"\x00", 1)[0]
    try:
        return s.decode("ascii", errors="ignore")
    except Exception:
        return ""

def _u16_pairs_at_page(conn, page: int, count_pairs: int = 2):
    """Read one page and split into little-endian uint16 pairs."""
    b = read_page_ultralight(conn, page)
    if b is None or len(b) != 4:
        return []
    return [(b[0] | (b[1] << 8)), (b[2] | (b[3] << 8))][:count_pairs]

def read_anycubic_fields(conn):
    """
    Best-effort parse of Anycubic tag layout as seen in field dumps:
    - SKU at pages 5.. (zero terminated)
    - Brand at page 10 (ASCII, zero-terminated in page)
    - Material at page 15 (ASCII, e.g. 'PLA+')
    - Several uint16 parameters at pages 23..31
    Returns a dict with parsed fields.
    """
    out = {}
    # Sanity: ensure connected
    try:
        atr = read_atr(conn)
        out["atr"] = atr
    except Exception:
        out["atr"] = b""

    # UID (if supported)
    uid, sw1, sw2 = read_uid(conn)
    if uid is not None:
        out["uid"] = uid

    # ASCII fields
    out["sku"] = _read_ascii_z(conn, start_page=5, max_len=32)  # e.g., 'AHPLPDB-106'
    # Brand: often 'AC' at page 10 (we read one page and strip zeros)
    b10 = read_page_ultralight(conn, 10) or b""
    out["brand"] = (b10.split(b"\x00", 1)[0].decode("ascii", errors="ignore") if b10 else "")

    # Material at page 15 (ASCII in one page)
    p15 = read_page_ultralight(conn, 15) or b""
    out["material"] = (p15.split(b"\x00", 1)[0].decode("ascii", errors="ignore") if p15 else "")

    # Parameter pages (tentative names)
    # Pages 23..31: treat as little-endian u16 pairs
    params = {}
    for pg in range(23, 32):
        vals = _u16_pairs_at_page(conn, pg, 2)
        if vals:
            params[f"p{pg}_a"] = vals[0]
            params[f"p{pg}_b"] = vals[1]
    out["params"] = params

    # Optional: raw snippets that looked important
    p20 = read_page_ultralight(conn, 20); out["p20_raw"] = p20  # maybe CRC/flags
    p40 = read_page_ultralight(conn, 40); out["p40_raw"] = p40
    p41 = read_page_ultralight(conn, 41); out["p41_raw"] = p41
    p42 = read_page_ultralight(conn, 42); out["p42_raw"] = p42

    return out

def interpret_anycubic(info: dict) -> dict:
    """
    Mappt bekannte Roh-Parameter auf sprechende Felder:
    - nozzle_temp_min_c / nozzle_temp_max_c     (aus p24_a / p24_b)
    - bed_temp_min_c / bed_temp_max_c           (aus p29_a / p29_b)
    - filament_diameter_mm                      (aus p30_a / 100)
    - spool_weight_g, spool_weight_kg           (aus p31_a / 1 bzw. /1000)
    - unknown_p30_b                             (p30_b bleibt unbekannt)
    Unbekanntes bleibt im 'params'-Block erhalten.
    """
    out = dict(info)
    params = info.get("params", {})

    nozzle_min = params.get("p24_a")
    nozzle_max = params.get("p24_b")
    bed_min    = params.get("p29_a")
    bed_max    = params.get("p29_b")
    p30_a      = params.get("p30_a")
    p30_b      = params.get("p30_b")
    p31_a      = params.get("p31_a")

    friendly = {}

    if nozzle_min is not None and nozzle_max is not None:
        friendly["nozzle_temp_min_c"] = nozzle_min
        friendly["nozzle_temp_max_c"] = nozzle_max

    if bed_min is not None and bed_max is not None:
        friendly["bed_temp_min_c"] = bed_min
        friendly["bed_temp_max_c"] = bed_max

    if isinstance(p30_a, int):
        # 175 -> 1.75 mm
        friendly["filament_diameter_mm"] = p30_a / 100.0

    if isinstance(p31_a, int):
        friendly["spool_weight_g"]  = p31_a
        friendly["spool_weight_kg"] = p31_a / 1000.0

    if p30_b is not None:
        # Noch unbekannt, aber sichtbar halten
        friendly["unknown_p30_b"] = p30_b

    out["friendly"] = friendly
    return out