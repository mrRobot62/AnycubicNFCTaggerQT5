# AnycubicNFCTaggerQT5 – Build Instructions

This document explains how to build **AnycubicNFCTaggerQT5** for both **macOS (.dmg)** and **Windows (.exe/.msi)** using the provided scripts.

---

## 🧩 Prerequisites

### Common Requirements
- Python **3.12.x** (installed and available in PATH)
- The following packages installed in your build environment:
  ```bash
  pip install -U setuptools wheel cx_Freeze dmgbuild PyQt5
  ```

---

## 🍎 macOS Build (.app / .dmg)

### 1. Location of the build script
Script: `build_dmg.sh`  
Located in the project root.

### 2. Purpose
Creates a clean **macOS .app** bundle using `cx_Freeze`, and then builds a **.dmg** image via `dmgbuild`.

### 3. Usage
Make the script executable:
```bash
chmod +x build_dmg.sh
```

Then run:
```bash
./build_dmg.sh
```

### 4. What it does
- Closes any running instance of the app.
- Cleans up old `build/` directories safely.
- Builds the app (`bdist_mac`).
- Generates a `.dmg` in `dist/` using your `packaging/macos/dmg_settings.py`.

### 5. Output
| File | Description |
|------|--------------|
| `build/AnycubicNFCTaggerQT5.app` | The application bundle |
| `dist/AnycubicNFCTaggerQT5-<version>-arm64.dmg` | macOS disk image for distribution |

### 6. Optional (signing and notarization)
The script already contains commented-out placeholders for:
- `codesign`
- `notarytool` submission and stapling

Uncomment these lines once you have a valid **Apple Developer ID**.

---

## 🪟 Windows Build (.exe / .msi)

### 1. Location of the build script
Script: `build_exe.bat`  
Located in the project root.

### 2. Purpose
Creates a clean Windows **portable EXE** and (optionally) an **MSI installer** using `cx_Freeze`.

### 3. Usage
Open **Command Prompt (cmd.exe)** and run:
```bat
build_exe.bat
```

### 4. Optional environment variables
| Variable | Description | Example |
|-----------|-------------|----------|
| `PYTHON_BIN` | Path to specific Python executable | `set PYTHON_BIN=C:\Python312\python.exe` |
| `DO_MSI` | Disable MSI build (set to `0` to skip) | `set DO_MSI=0` |

### 5. What it does
- Ensures Python and `cx_Freeze` are installed.
- Reads the project version from `pyproject.toml`.
- Cleans up `build/` and `dist/` directories.
- Runs `freeze_setup.py build_exe` to build a portable `.exe`.
- Optionally runs `freeze_setup.py bdist_msi` to create an installer.

### 6. Output
| File | Description |
|------|--------------|
| `build\AnycubicNFCTaggerQT5.exe` | Portable executable |
| `dist\AnycubicNFCTaggerQT5-<version>.msi` | Optional Windows installer |

---

## 🔧 Tips

- Always build **on the target platform** (macOS → .dmg, Windows → .exe/.msi).
- Ensure your Python environment has **no active GUI instances** during build (especially for macOS).
- On macOS, avoid opening the `build/` directory in Finder while building (QuickLook locks files).

---

## 📂 Summary

| Platform | Script | Output | Toolchain |
|-----------|---------|---------|------------|
| macOS | `build_dmg.sh` | `.app`, `.dmg` | `cx_Freeze` + `dmgbuild` |
| Windows | `build_exe.bat` | `.exe`, `.msi` | `cx_Freeze` |

---

**Author:** Bernhard Klein  
**Project:** AnycubicNFCTaggerQT5  
**Last Updated:** 2025‑10‑17
