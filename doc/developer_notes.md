# Developer Notes (Anycubic NFC QT5)

> This document explains, in simple English, how the UI pieces work together and how to add or change fields. It is written for non-native speakers. Short sentences. Direct wording.

---

## 1. Project parts (high level)

### Files you will touch most

- `ui/main_window.py`  
  The main application window.  
  - Talks to the NFC backend (`nfc/pcsc.py`).  
  - Shows filament + color comboboxes.  
  - Opens the Page Editor dock.  
  - Converts high-level values (SKU, material, color, temperatures) into **page bytes** and sends them to the Page Editor.

- `ui/docks/page_editor_dock.py`  
  The “Hex & ASCII” editor.  
  - One row per NFC page (4 bytes per page).  
  - You can type hex bytes or ASCII.  
  - You can mark rows with “Apply”.  
  - Buttons: **WRITE NFC**, **SIMULATE**, **CLEAR**, **DELETE (User Area)**.  
  - Emits signals to `MainWindow` when the user clicks buttons.

- `ui/nfc_fields.py`  
  Central map of **what lives where** on the tag.  
  - `PageSpan` describes a continuous block of pages: `start` + `pages`.  
  - Class `P` contains named fields (e.g., `P.SKU = PageSpan(0x05, 5)`).  
  - Small helper functions to convert values into bytes:  
    - `map_ascii_span(span, text)`  
    - `map_u16(span, value)`  
    - `map_color_rgba(span, hex_color)`  
    - `to_rgba_bytes(hex_color)`  
  - `PAGE_NAME_MAP`: optional human names for pages (for UI labels).

---

## 2. Data flow (important)

### A) When user clicks **READ NFC**

1. `MainWindow.on_read()` connects to the reader and calls `read_anycubic_fields()`.
2. It receives a dict like:
   ```python
   {
     "sku": "HTPCP-101",
     "manufacturer": "AC",
     "material": "TPU Filament",
     "color_hex": "#800080FF",
     "nozzle_temp_min_c": 210,
     ...
   }
   ```
3. `MainWindow` converts this **high-level info** into **page bytes** using the helpers from `nfc_fields.py`:
   - `map_ascii_span(P.SKU, info["sku"])`
   - `map_color_rgba(P.COLOR, info["color_hex"])`
   - `map_u16(P.NOZZLE_MIN, info["nozzle_temp_min_c"])`
   - etc.
4. It calls `page_dock.stage_pages(mapping, mark_changed=False)` to **prefill** the editor.  
   - `mark_changed=False` means: do **not** auto-check the “Apply” boxes.  
   - The user sees the pages filled, but nothing is “armed” to write yet.

### B) When user changes **Filament** or **Color** in the combos

1. `MainWindow.on_color_changed()` (or `on_filament_changed()`) builds a **staged mapping** again:
   - SKU goes to `P.SKU` (multi-page).
   - Manufacturer to `P.MANUFACTURER` (usually 1 page).
   - Material to `P.MATERIAL` (multi-page).
   - Color to `P.COLOR` (RGBA 4 bytes).
2. Calls `stage_pages(..., mark_changed=False)`.  
   The Page Editor updates rows **without** overwriting user edits that are already there.

### C) When user clicks **WRITE NFC** in the Page Editor

1. Dock collects rows where “Apply” is checked: `{page: bytes(4)}`.
2. Emits `writePagesRequested` with that payload.
3. `MainWindow._on_editor_write()` groups consecutive pages and calls `write_raw_pages()`.

> Important: Only **checked** rows are written. Prefill is safe.

---

## 3. Page model (PageSpan) and mapping helpers

### `PageSpan`

```python
@dataclass(frozen=True)
class PageSpan:
    start: int   # first page index, e.g. 0x05
    pages: int   # how many pages, e.g. 5 (20 bytes)
```

`P` is a small “schema”:

```python
class P:
    SKU          = PageSpan(0x05, 5)
    MANUFACTURER = PageSpan(0x10, 1)
    MATERIAL     = PageSpan(0x15, 8)
    COLOR        = PageSpan(0x20, 1)
    DIAMETER_CENTI = PageSpan(0x11, 1)
    NOZZLE_MIN     = PageSpan(0x12, 1)
    NOZZLE_MAX     = PageSpan(0x13, 1)
    BED_MIN        = PageSpan(0x14, 1)
    BED_MAX        = PageSpan(0x18, 1)
    WEIGHT_G       = PageSpan(0x31, 1)
```

### Mapping helpers

- **Text across multiple pages**  
  ```python
  map_ascii_span(P.SKU, "HTPCP-101")  # → {0x05: b'HTPC', 0x06: b'P-10', 0x07: b'1\x00\x00\x00', ...}
  ```
  Truncates or pads to fill pages. Uses ASCII only.

- **16-bit numbers (U16)**  
  ```python
  map_u16(P.NOZZLE_MIN, 210)  # → {0x12: b'\xD2\x00\x00\x00'}  # little-endian by default
  ```
  You can pass `byteorder="big"` if your tag uses big-endian.

- **Color as RGBA**  
  ```python
  map_color_rgba(P.COLOR, "#800080FF")  # → {0x20: b'\x80\x00\x80\xFF'}
  ```
  If alpha is missing, it adds `FF`.

---

## 4. Page Editor behavior

- One row per page:  
  `[✓ Apply] [0xPP (dec)] [Name] [B0] [B1] [B2] [B3] [ASCII]`
- Hex inputs accept 0..2 hex digits per cell.  
  ASCII is 4 characters (other chars ignored).
- Edits sync both ways: typing hex updates ASCII, typing ASCII updates hex.
