# Page Editor Dock

This chapter documents the **Page Editor** dock used to view and edit Mifare Ultralight pages
(4 bytes per page). It reflects the current implementation in `src/anycubic_nfc_qt5/ui/docks/page_editor_dock.py`.

## Overview

- One row per page with the following columns:
  - **Apply** (checkbox, tri‑state master in header)
  - **Page** (hex + decimal, e.g. `0x20 (32)`)
  - **Name** (friendly label if known)
  - **B0 B1 B2 B3** (editable hex bytes, with validation)
  - **ASCII** (printable ASCII for those 4 bytes)
- For the **color page** (default: `0x20`), the ASCII field accepts and shows **`#RRGGBBAA`**. It auto‑syncs with the 4 byte fields.

## Key behaviors

- **Hex ⇄ ASCII Sync**: Editing any hex byte updates ASCII; editing ASCII updates hex bytes.
- **Apply Master Checkbox**:
  - Header checkbox is **tri‑state**:
    - **Checked** → mark all rows
    - **Unchecked** → unmark all rows
    - **PartiallyChecked** → reflects a mixed state (set programmatically)
- **Buttons**:
  - **WRITE NFC**: Emits only rows marked with *Apply*.
  - **SIMULATE**: Emits **all** rows (for logging/testing).
  - **CLEAR**: Clears all rows to `00 00 00 00` and requests UI selection reset.
  - **DELETE (User Area)**: Shows a confirmation dialog (`Type 'RESET' ...`) before requesting a tag wipe.
  - **Mark Changed**: Marks rows that are **non‑zero**.
  - **Mark Known Fields**: Marks rows that have a known meaning (from `nfc_fields.PAGE_NAME_MAP`).

## Programmatic API (signals)

- `simulateRequested: dict` → `{{"pages": {{page:int -> bytes(4)}}}}` for **all** pages.
- `writePagesRequested: dict` → same payload, but only for **checked** pages.
- `deleteUserAreaRequested: ()` → request to wipe user area.
- `clearUiRequested: ()` → request to clear related UI selections.

## Prefill helpers

- `stage_pages(mapping, mark_changed=False)`: accepts either `{{page:int -> bytes}}` or `{{span:PageSpan -> bytes}}`.
  Bytes are chunked across pages (4 bytes/page). Optionally marks rows as changed.
- `stage_prefill_bytes_range(start_page, payload, override=False, max_pages=None)`
- `stage_prefill_ascii_range(start_page, text, override=False, max_pages=None)`

## Validation & Formatting

- Hex byte fields use a regex validator: `^(?:0x)?[0-9A-Fa-f]{0,2}$`.
- ASCII field shows printable ASCII (non‑printables dropped).
- Color page ASCII supports `#RRGGBB` and `#RRGGBBAA`. Internally stored as RGBA bytes (`0xR 0xG 0xB 0xA`).

## Tips

- Use **Mark Known Fields** to quickly target the fields that belong to the Anycubic tag layout.
- Use **SIMULATE** to preview the raw page map in logs without writing to a physical tag.
