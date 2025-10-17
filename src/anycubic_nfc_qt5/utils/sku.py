# src/anycubic_nfc_qt5/utils/sku.py
import re

def sku_base(sku: str) -> str:
    """Return alphanumeric part before '-', e.g. 'AHHSCG-101' -> 'AHHSCG'."""
    if not sku:
        return ""
    head = sku.split("-", 1)[0]
    return re.sub(r"[^A-Za-z0-9]", "", head)