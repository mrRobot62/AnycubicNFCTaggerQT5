# tests/test_nfc_probe.py
# Simple hardware smoke test for a PC/SC NFC reader:
# - list readers
# - wait for a tag
# - print ATR and try to read UID (if supported)

import sys
import time
from typing import Optional

import pytest

from anycubic_nfc_qt5.nfc.pcsc import list_readers, wait_for_card, read_atr, read_uid


def _fmt_bytes(b: bytes) -> str:
    """Format bytes as hex string with spaces."""
    return " ".join(f"{x:02X}" for x in b)


@pytest.mark.hardware
def test_nfc_probe_interactive():
    """Interactive probe: skip if no reader; waits up to 30s for a card."""
    rlist = list_readers()
    if not rlist:
        pytest.skip("No PC/SC reader found. Install drivers / start pcscd (macOS).")

    print(f"[INFO] Found readers: {[str(r) for r in rlist]}")
    print("[INFO] Waiting for a card (30s timeout). Place a tag on the reader...")

    conn = wait_for_card(timeout_s=30.0, poll_interval_s=0.5)
    if conn is None:
        pytest.skip("No card detected within timeout.")

    atr = read_atr(conn)
    print(f"[OK] ATR: { _fmt_bytes(atr) if atr else '(empty)' }")

    uid, sw1, sw2 = read_uid(conn)
    if uid is not None:
        print(f"[OK] UID: { _fmt_bytes(uid) }  (SW={sw1:02X}{sw2:02X})")
    else:
        print(f"[WARN] UID command not supported or failed (SW={sw1:02X}{sw2:02X}).")
    assert True  # We don't hard-fail on missing UID support.


if __name__ == "__main__":
    # Allow running as a standalone script without pytest:
    rlist = list_readers()
    if not rlist:
        print("[ERROR] No PC/SC reader found. On macOS: `brew install pcsc-lite` and `brew services start pcscd`.")
        sys.exit(0)

    print(f"[INFO] Found readers: {[str(r) for r in rlist]}")
    print("[INFO] Waiting for a card (30s timeout). Place a tag on the reader...")
    conn = wait_for_card(timeout_s=30.0, poll_interval_s=0.5)
    if conn is None:
        print("[WARN] No card detected within timeout.")
        sys.exit(0)

    atr = read_atr(conn)
    print(f"[OK] ATR: { _fmt_bytes(atr) if atr else '(empty)' }")

    uid, sw1, sw2 = read_uid(conn)
    if uid is not None:
        print(f"[OK] UID: { _fmt_bytes(uid) }  (SW={sw1:02X}{sw2:02X})")
    else:
        print(f"[WARN] UID read failed or unsupported (SW={sw1:02X}{sw2:02X}).")