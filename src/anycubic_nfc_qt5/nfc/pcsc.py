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

# --- Low-level helpers for Anycubic layout ---
def _read_u16_at(conn, page: int, byte_offset: int) -> int | None:
    """Read little-endian uint16 at page+offset (offset 0 or 2)."""
    b = read_page_ultralight(conn, page)
    if not b or byte_offset not in (0, 2):
        return None
    lo = b[byte_offset]
    hi = b[byte_offset + 1]
    return lo | (hi << 8)

def _read_string_page(conn, page: int, max_len: int = 32) -> str:
    """Read zero-terminated ASCII starting at given page (4 bytes/page)."""
    buf = bytearray()
    p = page
    while len(buf) < max_len:
        q = read_page_ultralight(conn, p)
        if not q:
            break
        buf.extend(q)
        if 0x00 in q:
            break
        p += 1
    return bytes(buf).split(b"\x00", 1)[0].decode("ascii", errors="ignore")

def _read_color_rgba_hex(conn, page: int) -> str | None:
    """Read 4 bytes at page and return '#RRGGBBAA'.
    Many tags store bytes in reverse order; using reversed bytes is robust."""
    b = read_page_ultralight(conn, page)
    if not b or len(b) != 4:
        return None
    # Reverse to get RGBA: [R,G,B,A] = reversed([b0,b1,b2,b3])
    r, g, b_, a = reversed(b)
    return f"#{r:02X}{g:02X}{b_:02X}{a:02X}"

def read_anycubic_fields(conn):
    """
    Parse Anycubic raw layout (Type 2 / NTAG):
      - SKU: pages 5.. (zero-terminated ASCII)
      - manufacturer: page 0x0A (10), ASCII
      - material: page 0x0F (15), ASCII (z.B. 'PLA+', 'ASA')
      - color: page 0x14 (20), 4 bytes -> '#RRGGBBAA'
      - ranges A,B,C: pages 0x17..0x1C (23..28), u16 pairs (little-endian)
      - bed: page 0x1D (29), u16@0=min, u16@2=max
      - diameter/length: page 0x1E (30), dia=(u16@0)/100, length=u16@2
      - weight: page 0x1F (31), u16@0 (grams)
    Plus: ATR/UID (wenn verfügbar) und ein 'params' Roh-Block fürs Debugging.
    """
    out = {}

    # ATR + UID
    try:
        out["atr"] = read_atr(conn) or b""
    except Exception:
        out["atr"] = b""
    uid, sw1, sw2 = read_uid(conn)
    if uid is not None:
        out["uid"] = uid

    # ASCII strings
    out["sku"] = _read_ascii_z(conn, start_page=5, max_len=32)  # bereits vorhanden
    out["manufacturer"] = _read_string_page(conn, 0x0A, 16) or ""
    out["material"] = _read_string_page(conn, 0x0F, 16) or ""

    # Color
    out["color_hex"] = _read_color_rgba_hex(conn, 0x14)  # '#RRGGBBAA' or None

    # Ranges A/B/C (speed/nozzle)
    def _range_tuple(p_speed: int, p_noz: int) -> dict:
        return {
            "speed_min": _read_u16_at(conn, p_speed, 0),
            "speed_max": _read_u16_at(conn, p_speed, 2),
            "nozzle_min": _read_u16_at(conn, p_noz, 0),
            "nozzle_max": _read_u16_at(conn, p_noz, 2),
        }

    out["range_a"] = _range_tuple(0x17, 0x18)
    out["range_b"] = _range_tuple(0x19, 0x1A)
    out["range_c"] = _range_tuple(0x1B, 0x1C)

    # Bed temps
    out["bed_min"] = _read_u16_at(conn, 0x1D, 0)
    out["bed_max"] = _read_u16_at(conn, 0x1D, 2)

    # Diameter / Length / Weight
    dia_raw = _read_u16_at(conn, 0x1E, 0)
    out["diameter_mm"] = (dia_raw / 100.0) if isinstance(dia_raw, int) else None
    out["length_m"] = _read_u16_at(conn, 0x1E, 2)  # meters (typ. ~330)
    out["weight_g"] = _read_u16_at(conn, 0x1F, 0)  # grams (typ. 1000)

    # Keep existing 'params' for backward-compat / debugging:
    params = {}
    for pg in range(23, 32):
        b = read_page_ultralight(conn, pg)
        if b:
            lo = b[0] | (b[1] << 8)
            hi = b[2] | (b[3] << 8)
            params[f"p{pg}_a"] = lo
            params[f"p{pg}_b"] = hi
    out["params"] = params

    # Raw bytes we previously surfaced as dbg
    out["p20_raw"] = read_page_ultralight(conn, 20)
    out["p40_raw"] = read_page_ultralight(conn, 40)
    out["p41_raw"] = read_page_ultralight(conn, 41)
    out["p42_raw"] = read_page_ultralight(conn, 42)

    return out

def interpret_anycubic(info: dict) -> dict:
    """Human-friendly mapping with the new fields."""
    out = dict(info)
    friendly = {}

    # Direct fields
    if info.get("diameter_mm") is not None:
        friendly["filament_diameter_mm"] = info["diameter_mm"]
    if info.get("weight_g") is not None:
        friendly["spool_weight_g"] = info["weight_g"]
        friendly["spool_weight_kg"] = info["weight_g"] / 1000.0
    if info.get("bed_min") is not None and info.get("bed_max") is not None:
        friendly["bed_temp_min_c"] = info["bed_min"]
        friendly["bed_temp_max_c"] = info["bed_max"]

    # Prefer „range_a“ als Hauptbereich (falls gesetzt), sonst b/c als Fallback
    def pick_range(*ranges):
        for r in ranges:
            if r and r.get("nozzle_min") is not None and r.get("nozzle_max") is not None:
                return r
        return None

    rpick = pick_range(info.get("range_a"), info.get("range_b"), info.get("range_c"))
    if rpick:
        friendly["nozzle_temp_min_c"] = rpick["nozzle_min"]
        friendly["nozzle_temp_max_c"] = rpick["nozzle_max"]
        if rpick.get("speed_min") is not None and rpick.get("speed_max") is not None:
            friendly["speed_min"] = rpick["speed_min"]
            friendly["speed_max"] = rpick["speed_max"]

    # Keep also the full ranges block for UI/debug
    friendly["ranges"] = {
        "A": info.get("range_a"),
        "B": info.get("range_b"),
        "C": info.get("range_c"),
    }

    # Color passt sauber aus info['color_hex']
    if info.get("color_hex"):
        friendly["color_hex"] = info["color_hex"]

    out["friendly"] = friendly
    return out


# --- Ultralight / NTAG write helpers (PC/SC UPDATE BINARY) ---

def write_page_ultralight(conn, page: int, data4: bytes) -> tuple[bool, int, int]:
    """Write exactly 4 bytes to one NTAG/Ultralight page using PC/SC UPDATE BINARY.
    Returns (ok, sw1, sw2)."""
    if not isinstance(data4, (bytes, bytearray)) or len(data4) != 4:
        raise ValueError("write_page_ultralight expects exactly 4 bytes")
    # APDU: FF D6 00 <page> 04 <4 bytes>
    apdu = [0xFF, 0xD6, 0x00, page & 0xFF, 0x04] + list(data4)
    data, sw1, sw2 = conn.transmit(apdu)
    return (sw1 == 0x90 and sw2 == 0x00), sw1, sw2


def write_ascii_z(conn, start_page: int, text: str, max_len: int = 32) -> bool:
    """Write a zero-terminated ASCII string across pages.
    Writes (min(len(text), max_len)) + 1 (terminator) bytes."""
    raw = (text or "").encode("ascii", errors="ignore")[:max_len] + b"\x00"
    # Write in 4-byte chunks
    ok_all = True
    for i in range(0, len(raw), 4):
        chunk = raw[i:i+4]
        if len(chunk) < 4:
            chunk = chunk + b"\x00"*(4-len(chunk))
        page = start_page + (i // 4)
        ok, sw1, sw2 = write_page_ultralight(conn, page, chunk)
        if not ok:
            ok_all = False
            break
    return ok_all


def write_color_rgba_hex(conn, page: int, color_hex: str) -> bool:
    """Write color at one page as 4 bytes in 'tag order' (ABGR as seen on dumps),
    taking '#RRGGBB' or '#RRGGBBAA' and converting to bytes accordingly.
    We store in the same order we observed while reading (reverse when needed)."""
    s = (color_hex or "").strip().lstrip("#")
    if len(s) not in (6, 8):
        return False
    if len(s) == 6:
        s = s + "FF"  # default alpha
    # We read back as reversed bytes -> to write the same representation, reverse here
    # Read-side used: r,g,b,a = reversed(b)
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    a = int(s[6:8], 16)
    # Tag stores as [A, B, G, R] in the dumps we saw
    data = bytes([a, b, g, r])
    ok, sw1, sw2 = write_page_ultralight(conn, page, data)
    return ok


# --- High-level write spec for future extension ---

def write_anycubic_basic(conn, *, sku: str, manufacturer: str, material: str, color_hex: str) -> dict:
    """Write the basic Anycubic fields:
       - p05.. : SKU (zero-terminated ASCII)
       - p0A   : manufacturer (ASCII, 2 chars recommended)
       - p0F   : material (ASCII)
       - p14   : color as 4 bytes (ABGR as per dumps), from '#RRGGBB' or '#RRGGBBAA'
       Returns a dict with per-field success flags."""
    results = {
        "p05_sku": False,
        "p0A_manu": False,
        "p0F_mat": False,
        "p14_color": False,
    }
    try:
        # SKU at page 5
        results["p05_sku"] = write_ascii_z(conn, 0x05, sku, max_len=32)
        # Manufacturer at page 0x0A (10)
        # keep it short (2–4 bytes). Excess is truncated by write_ascii_z.
        results["p0A_manu"] = write_ascii_z(conn, 0x0A, manufacturer, max_len=8)
        # Material at page 0x0F (15)
        results["p0F_mat"]  = write_ascii_z(conn, 0x0F, material, max_len=16)
        # Color at page 0x14 (20)
        results["p14_color"] = write_color_rgba_hex(conn, 0x14, color_hex)
    except Exception:
        # Leave flags as-is; caller can inspect
        pass
    return results

def write_anycubic_params(conn, *, 
                          range_a=None, range_b=None, range_c=None,
                          bed_min=None, bed_max=None,
                          diameter_mm=None, length_m=None, weight_g=None) -> dict:
    """Write optional parameters; each range = dict with speed_min/speed_max/nozzle_min/nozzle_max."""
    results = {}
    # TODO: fill with write_bytes helpers similar to read_u16_at (use write_page_ultralight + little-endian packing)
    return results


# --- Ergänzungen in anycubic_nfc_qt5/nfc/pcsc.py ---

# Kleinere Hilfen
def _cmd_read_page(page: int):
    # MIFARE Ultralight/NTAG READ: 0x30, lese 16 Bytes (4 Pages)
    return [0xFF, 0xB0, 0x00, page & 0xFF, 0x10]  # PC/SC direct-transmit variiert je nach Reader;
                                                  # falls deine read_uid/read_anycubic_fields anders senden,
                                                  # passe diesen Wrapper auf euren Transmit-Flow an.

def _cmd_write_page(page: int, data4: bytes):
    # MIFARE Ultralight/NTAG WRITE: 0xA2, 4 Bytes
    data4 = (data4 or b"\x00\x00\x00\x00")[:4]
    while len(data4) < 4:
        data4 += b"\x00"
    return [0xFF, 0xD6, 0x00, page & 0xFF, 0x04] + list(data4)

def _tx(conn, apdu: list[int]):
    data, sw1, sw2 = conn.transmit(apdu)
    return bytes(data), sw1, sw2

def read_single_page(conn, page: int) -> bytes:
    """
    Liest eine einzelne 4-Byte-Page robust, indem ein 16-Byte-READ (4 Pages) gemacht wird
    und die relevante Page ausgeschnitten wird.
    """
    # 16-Byte-READ ab Start-Page-Gruppe
    base = page & ~0x03
    data, sw1, sw2 = _tx(conn, _cmd_read_page(base))
    if sw1 != 0x90:
        raise RuntimeError(f"READ failed for page 0x{page:02X}: SW1/SW2={sw1:02X}/{sw2:02X}")
    off = (page & 0x03) * 4
    chunk = bytes(data)[off:off+4]
    if len(chunk) < 4:
        chunk += b"\x00"*(4-len(chunk))
    return chunk

def detect_user_area(conn) -> dict:
    """
    Sehr konservative Heuristik für NTAG/Ultralight:
    - Liefert dict: {"user_start": int, "user_end": int_exclusive, "protected": set_of_pages}
    - Falls nicht ermittelbar, fällt zurück auf übliche NTAG213-Defaults.
    """
    info = {
        "user_start": 0x04,   # oft ab 0x04 userdaten (nach header 0x00..0x03)
        "user_end":   0x29,   # exklusiv, d. h. 0x04..0x28 (NTAG213 typisch ~0x29 Ende, 0x2A.. Lock/CFG)
        "protected": set([0x00, 0x01, 0x02, 0x03,  # UID/LOCK/CFG Header
                          0x2A, 0x2B, 0x2C, 0x2D]) # Lock/OTP/CFG (variiert je nach Tag)
    }
    try:
        # Wenn du eine GET_VERSION/CC-Parser hast, nutze ihn hier um user_end dynamisch zu erkennen.
        # Für jetzt: best-effort. Optional: lese CC bei 0x03 und leite Größe ab.
        pass
    except Exception:
        pass
    return info

def write_raw_pages(conn, start_page: int, data_bytes: bytes, skip_protected: bool = True, delay_ms: int = 5):
    """
    Schreibt ab start_page die Daten byteweise über 4-Byte-Pages (0xA2).
    Sicherheits-Geländer:
      - skip_protected=True: überspringt bekannte kritische Pages automatisch
      - respektiert detect_user_area()

    Rückgabe:
      dict {page:int -> True/False} pro tatsächlich geschriebenem Page-Versuch
      oder {} wenn nichts zu schreiben war.
    """
    result = {}
    buf = bytes(data_bytes or b"")
    if len(buf) == 0:
        return result

    ua = detect_user_area(conn)
    protected = set(ua.get("protected", set()))

    # Auf 4-Byte Pages aufteilen
    pages = (len(buf) + 3) // 4
    for i in range(pages):
        p = start_page + i
        # 4-Byte-Scheibe
        slice4 = buf[i*4:(i+1)*4]
        if len(slice4) < 4:
            slice4 += b"\x00"*(4-len(slice4))

        # Schutz prüfen
        if skip_protected and p in protected:
            result[p] = False
            continue
        # optional: user-area begrenzen
        user_start = ua.get("user_start", 0)
        user_end = ua.get("user_end", 0x100)
        if not (user_start <= p < user_end):
            # außerhalb User-Bereich -> als "übersprungen/nicht erlaubt"
            result[p] = False
            continue

        # tatsächlicher Write
        try:
            _, sw1, sw2 = _tx(conn, _cmd_write_page(p, slice4))
            ok = (sw1 == 0x90)
            result[p] = ok
            if delay_ms:
                QtCore.QThread.msleep(delay_ms)
        except Exception:
            result[p] = False

    return result

def clear_user_area(conn) -> dict:
    """
    Setzt die komplette User-Area (detect_user_area) auf 0x00.
    Rückgabe: dict page->bool.
    """
    ua = detect_user_area(conn)
    user_start = ua.get("user_start", 0x04)
    user_end = ua.get("user_end", 0x29)
    result = {}
    for p in range(user_start, user_end):
        try:
            _, sw1, sw2 = _tx(conn, _cmd_write_page(p, b"\x00\x00\x00\x00"))
            result[p] = (sw1 == 0x90)
            QtCore.QThread.msleep(3)
        except Exception:
            result[p] = False
    return result


# --- Additions for raw page read/write and user-area clearing ---

from PyQt5 import QtCore

def _cmd_read_page_group(start_page: int):
    """
    PC/SC wrapper to read 4 pages (16 bytes) starting at start_page & ~0x03.
    NOTE: Some readers expect native 0x30; adjust if your stack differs.
    """
    return [0xFF, 0xB0, 0x00, start_page & 0xFF, 0x10]

def _cmd_write_single_page(page: int, data4: bytes):
    """
    PC/SC wrapper to write a single 4-byte page.
    """
    d = (data4 or b"\x00\x00\x00\x00")[:4]
    while len(d) < 4:
        d += b"\x00"
    return [0xFF, 0xD6, 0x00, page & 0xFF, 0x04] + list(d)

def _tx(conn, apdu: list):
    data, sw1, sw2 = conn.transmit(apdu)
    return bytes(data), sw1, sw2

def read_single_page(conn, page: int) -> bytes:
    """
    Reads a single 4-byte page by issuing a 16-byte read for the page group.
    """
    base = page & ~0x03
    data, sw1, sw2 = _tx(conn, _cmd_read_page_group(base))
    if sw1 != 0x90:
        raise RuntimeError(f"READ failed for page 0x{page:02X}: SW1/SW2={sw1:02X}/{sw2:02X}")
    off = (page & 0x03) * 4
    chunk = data[off:off+4]
    if len(chunk) < 4:
        chunk += b"\x00" * (4 - len(chunk))
    return chunk

def detect_user_area(conn) -> dict:
    """
    Conservative heuristic for NTAG/Ultralight tags.
    Returns: {"user_start": int, "user_end": int_exclusive, "protected": set_of_pages}
    """
    info = {
        "user_start": 0x04,   # typical after header 0x00..0x03
        "user_end":   0x29,   # exclusive end (0x04..0x28)
        "protected": set([0x00, 0x01, 0x02, 0x03, 0x2A, 0x2B, 0x2C, 0x2D]),
    }
    # TODO: read CC / GET_VERSION to determine exact size if needed
    return info

def write_raw_pages(conn, start_page: int, data_bytes: bytes, skip_protected: bool = True, delay_ms: int = 5):
    """
    Writes data_bytes across 4-byte pages starting at start_page.
    Respects detect_user_area(); optionally skips protected pages.
    Returns dict {page:int -> bool} for attempted writes.
    """
    result = {}
    buf = bytes(data_bytes or b"")
    if len(buf) == 0:
        return result

    ua = detect_user_area(conn)
    protected = set(ua.get("protected", set()))
    user_start = ua.get("user_start", 0x04)
    user_end = ua.get("user_end", 0x29)

    pages = (len(buf) + 3) // 4
    for i in range(pages):
        p = start_page + i
        slice4 = buf[i*4:(i+1)*4]
        if len(slice4) < 4:
            slice4 += b"\x00" * (4 - len(slice4))

        if not (user_start <= p < user_end):
            result[p] = False
            continue
        if skip_protected and p in protected:
            result[p] = False
            continue

        try:
            _, sw1, sw2 = _tx(conn, _cmd_write_single_page(p, slice4))
            ok = (sw1 == 0x90)
            result[p] = ok
            if delay_ms:
                QtCore.QThread.msleep(delay_ms)
        except Exception:
            result[p] = False

    return result

def clear_user_area(conn) -> dict:
    """
    Clears the entire user area to 0x00. Returns dict page->bool.
    """
    ua = detect_user_area(conn)
    user_start = ua.get("user_start", 0x04)
    user_end = ua.get("user_end", 0x29)
    result = {}
    for p in range(user_start, user_end):
        try:
            _, sw1, sw2 = _tx(conn, _cmd_write_single_page(p, b"\x00\x00\x00\x00"))
            result[p] = (sw1 == 0x90)
            QtCore.QThread.msleep(3)
        except Exception:
            result[p] = False
    return result