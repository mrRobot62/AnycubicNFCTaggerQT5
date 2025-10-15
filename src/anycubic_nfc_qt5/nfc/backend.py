# src/anycubic_nfc_qt5/nfc/backend.py
from typing import Callable, Optional

try:
    from smartcard.System import readers
except Exception:
    readers = None  # pyscard nicht vorhanden

class NFCBackend:
    """
    Minimaler NFC-Wrapper. Hier kannst du später deine vorhandene Logik
    (Seiten lesen/schreiben etc.) aus deinem Projekt integrieren.
    """
    def __init__(self, on_log: Optional[Callable[[str], None]] = None):
        self.on_log = on_log or (lambda m: None)

    def _log(self, msg: str):
        self.on_log(msg)

    def read_card(self) -> Optional[bytes]:
        if readers is None:
            self._log("pyscard nicht gefunden – installiere 'pyscard' und PC/SC-Treiber.")
            return None
        try:
            rlist = readers()
            if not rlist:
                self._log("Kein Reader gefunden.")
                return None
            rd = rlist[0]
            self._log(f"Nutze Reader: {rd}")
            conn = rd.createConnection()
            conn.connect()
            # Hier würdest du echte APDUs senden und Daten sammeln
            # Für den Start: gib den ATR zurück.
            response, sw1, sw2 = conn.getATR(), 0x90, 0x00
            if sw1 == 0x90 and sw2 == 0x00:
                self._log("ATR empfangen.")
                return bytes(response)
            return None
        except Exception as e:
            self._log(f"Lesefehler: {e}")
            return None

    def write_card(self, payload: bytes) -> bool:
        if readers is None:
            self._log("pyscard nicht gefunden – installiere 'pyscard' und PC/SC-Treiber.")
            return False
        try:
            rlist = readers()
            if not rlist:
                self._log("Kein Reader gefunden.")
                return False
            rd = rlist[0]
            self._log(f"Nutze Reader: {rd}")
            conn = rd.createConnection()
            conn.connect()
            # TODO: hier echte Schreib-APDUs implementieren
            self._log(f"Simuliert geschrieben: {payload!r}")
            return True
        except Exception as e:
            self._log(f"Schreibfehler: {e}")
            return False