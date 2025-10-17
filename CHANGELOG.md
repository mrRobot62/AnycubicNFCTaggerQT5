# Changelog

This file summarizes key version milestones of **AnycubicNFCTaggerQT5**.

---

## v0.3.0 (Current - October 2025)

- Implemented **Page Editor Dock** with tri-state Apply and color `#RRGGBBAA` support.
- Added “Mark Changed” and “Mark Known Fields” buttons.
- Added full **dmgbuild**-based macOS packaging.
- Added **freeze_setup.py** for cx_Freeze builds (macOS & Windows).
- Added **packaging/macos/dmg_settings.py** auto-discovery for `.app` bundles.
- Introduced unified documentation set (INSTALLATION, BUILDING-BINARIES, USER_GUIDE, PACKAGING_SIGNING).

## v0.2.x (Earlier Prototype)

- Initial GUI implementation using PyQt5.
- Basic NFC read/write support via pyscard.
- No binary distribution yet (run-from-source only).

## v0.1.x (Pre-release Prototype)

- Proof-of-concept for Anycubic filament tag reading.
- Minimal GUI and single-page hex view.

---

**Next planned milestone: v0.4.0**
- Integrate enhanced tag templates (auto-fill).
- Add import/export of page maps.
- Introduce preference persistence and theme selector.
