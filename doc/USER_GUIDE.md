# User Guide

This guide explains how to use **AnycubicNFCTaggerQT5** as an end-user to read, modify, and write NFC filament tags.

> This document focuses on the graphical interface. Developer-oriented details are available in the Page Editor Dock and Build documentation.

---

## 1) Starting the Application

After installation or extraction of the binary:

- On **macOS**: open `AnycubicNFCTaggerQT5.app` (from `/Applications` or DMG copy).
- On **Windows**: double-click `AnycubicNFCTaggerQT5.exe`.

When the application starts, it automatically tries to detect an NFC reader connected via USB.

---

## 2) Initial Screens

### No NFC Reader Found
If no reader is detected, the start screen displays a message like:
> “No NFC-Reader found”

Check USB connection and drivers, then restart the app.

### Reader Found, No Tag Present
When the reader is detected but no NFC tag is placed on it, the UI remains idle, waiting for a tag.

---

## 3) Reading a Tag

1. Place an Anycubic NFC tag on the reader.
2. The tag’s memory pages (e.g., 0x00–0x2C) are read and displayed in the **Page Editor Dock**.
3. Known fields (e.g., filament name, color, manufacturer info) are highlighted with readable names.

---

## 4) Editing Tag Data

The **Page Editor Dock** allows modifying page data in multiple ways:

- Directly edit hex byte values (`B0–B3`).
- Enter printable ASCII text for fields (auto-synchronizes with bytes).
- For the color page (`0x20`), you can enter a color string in `#RRGGBBAA` format (e.g., `#FF8000FF`).

To prepare changes for writing:

- Tick the **Apply** checkbox for desired pages (or use the header checkbox to toggle all).

---

## 5) Writing Changes to NFC Tag

Click **WRITE NFC**:
- Only pages marked with “Apply” are written.
- The status log (or main window output) confirms success or reports write errors.

> Tip: Always verify the written data by re-reading the tag.

---

## 6) Simulation and Clear Operations

- **SIMULATE**: Emits all page data to the log window (for inspection). Does not touch the physical tag.
- **CLEAR**: Resets all fields in the editor to `00 00 00 00` and requests clearing related filament/color selections.

---

## 7) Deleting User Area

To delete (reset) user memory:

1. Click **DELETE (User Area)**.
2. Confirm by typing `RESET` in the dialog.
3. The app will issue a write operation setting all user pages to zero.

> ⚠️ This cannot be undone. Only perform on test tags or intentionally resettable tags.

---

## 8) Recommended Workflow

1. Insert tag and verify readout.
2. Use “Mark Known Fields” to auto-select meaningful data fields.
3. Adjust only required values (e.g., color, spool length, temperature data).
4. Press **WRITE NFC** to save changes.
5. Re-scan tag to verify integrity.

---

## 9) Troubleshooting

| Issue | Possible Cause | Solution |
|-------|----------------|-----------|
| “No NFC Reader found” | Reader disconnected or driver missing | Reconnect USB, reinstall PC/SC drivers |
| Write fails | Tag not supported or locked | Try another tag, or unlock if possible |
| Wrong colors or text | Encoding mismatch | Ensure ASCII or `#RRGGBBAA` input only |
| App window missing text/icons | Missing Qt resource | Reinstall or rebuild app |

---

**End of User Guide**
