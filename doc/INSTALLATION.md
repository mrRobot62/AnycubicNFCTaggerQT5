# Installation Guide

This document describes how to set up a development environment for **AnycubicNFCTaggerQT5** (v0.3.0) on macOS and Windows,
and how to run the application from source.

> Source code and comments are in **English**. Regular discussion remains in German.

---

## 1) Prerequisites

- **Python**: 3.12.x recommended.
- **Git** (optional, if cloning the repository).
- **Qt / PyQt5**: Installed automatically via `pip` (dependency in `pyproject.toml`).
- **NFC (pyscard)**: `pyscard` is declared as a dependency; on macOS and Windows it should install prebuilt wheels.
  If it fails, consult pyscard docs for platform-specific PC/SC drivers.

---

## 2) Create and activate a virtual environment

### macOS / Linux
```bash
python -m venv .venv
source .venv/bin/activate
```

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

## 3) Install dependencies

The project uses `pyproject.toml` with `project.dependencies`. Install them via:

```bash
python -m pip install --upgrade pip wheel setuptools
python -m pip install -e .
```

> If `-e .` is not desired, you can install dependencies explicitly:
> ```bash
> python -m pip install "PyQt5>=5.15,<6" "pyscard>=2.0"
> ```

---

## 4) Run from source

```bash
python -m anycubic_nfc_qt5.app
# or
python src/anycubic_nfc_qt5/app.py
```

If the GUI starts, you are ready to develop and test.

---

## 5) Next steps

- To build distributables, see **BUILDING-BINARIES.md**.
- To learn about the Page Editor, see **PAGE_EDITOR_DOCK.md**.
