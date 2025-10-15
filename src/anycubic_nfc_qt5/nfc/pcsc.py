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