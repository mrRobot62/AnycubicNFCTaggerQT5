# Building Binaries (macOS DMG & Windows EXE)

This document explains how to build **AnycubicNFCTaggerQT5** into
distributable binaries for macOS (DMG containing a `.app`) and Windows (standalone `.exe`, optional MSI).
It assumes you already have the repository checked out and that you will run the commands **from the project root**.

> Notes
>
> - Source code and comments are in **English**; regular discussion is in German.
> - Packaging is based on **cx_Freeze** (via our `freeze_setup.py`) for the app/executable creation, and **dmgbuild** for macOS DMGs.
> - The macOS DMG configuration lives in `packaging/macos/dmg_settings.py` and automatically discovers the built `.app` under `build/`.
> - Python 3.12 is supported in our current setup; adjust paths if you use a different Python version.
>
> If you run into issues, see the **Troubleshooting** section at the end.

---

## 1) Common prerequisites

- **Python**: 3.12.x recommended (matching your dev environment).
- **Pip / Build tools**:
  ```bash
  python -m pip install --upgrade pip wheel setuptools
  ```
- **Project dependencies (minimal)**:
  ```bash
  # From project root:
  python -m pip install -r requirements.txt
  # Plus build-time tools:
  python -m pip install cx-Freeze dmgbuild
  ```

> Tip: Use a **virtual environment** to isolate build dependencies.
>
> ```bash
> python -m venv .venv
> source .venv/bin/activate   # macOS/Linux
> .venv\Scripts\activate    # Windows (PowerShell or CMD)
> ```

---

## 2) macOS: build `.app` and create `.dmg`

### 2.1 Build the `.app` with cx_Freeze (via `freeze_setup.py`)

From the project root, run:

```bash
# Clean previous build artifacts (optional but recommended):
rm -rf build dist

# Build the app bundle via cx_Freeze setup
python freeze_setup.py build
```

- cx_Freeze creates an **.app bundle** under a path like:
  - `build/AnycubicNFCTaggerQT5.app` (if configured that way), or
  - `build/exe.macosx-<arch>-<pyver>/AnycubicNFCTaggerQT5.app`

> Our `packaging/macos/dmg_settings.py` is designed to **auto-locate** the first `.app` bundle found under `build/`,
> so you usually don't need to pass it explicitly to `dmgbuild`.

### 2.2 Create the `.dmg` with dmgbuild

```bash
# Ensure dist/ exists
mkdir -p dist

# Create the DMG; the title appears in Finder when opening the image
python -m dmgbuild -s packaging/macos/dmg_settings.py "AnycubicNFCTaggerQT5" dist/AnycubicNFCTaggerQT5.dmg
```

This produces a signed/unsigned **DMG** (depending on your dmgbuild/signing setup) at:
```
dist/AnycubicNFCTaggerQT5.dmg
```

#### (Optional) Code signing & notarization
If you plan to distribute to other Macs without security prompts:

1. **Sign** the `.app` and/or DMG with your Developer ID certificate.
2. **Notarize** with Apple and **staple** the ticket.
3. If you already have signing hooks in your dmgbuild settings, ensure your keychain and environment are set up before running the command.

> Detailed signing/notarization steps vary per environment and certificate setup, so they are not included here.

### 2.3 Verify the DMG

- Mount the DMG (double-click) and drag the `AnycubicNFCTaggerQT5.app` into `/Applications`.
- Launch the app and confirm it starts without warnings (or with expected macOS Gatekeeper prompts if unsigned).
- If you see missing library errors, check the **Troubleshooting** section.

---

## 3) Windows: build standalone `.exe` (and optional MSI)

### 3.1 Build the executable with cx_Freeze (via `freeze_setup.py`)

Open **PowerShell** (or CMD) in the project root:

```powershell
# Optional cleanup
rmdir /s /q build dist 2>$null

# Build with cx_Freeze setup
python .\freeze_setup.py build
```

Typical output:
```
build\exe.win-amd64-3.12\AnycubicNFCTaggerQT5.exe
```
The `exe.win-amd64-3.12` folder contains all required DLLs and files to run the application on another Windows machine (without Python). You can zip this folder for distribution, or continue to create an MSI installer.

### 3.2 (Optional) Create an MSI installer

If `freeze_setup.py` defines the `bdist_msi` command, you can run:

```powershell
python .\freeze_setup.py bdist_msi
```
The generated MSI will be placed under `dist\`.

### 3.3 Verify the Windows build

- Test the `AnycubicNFCTaggerQT5.exe` on a clean Windows VM.
- Confirm NFC-related features that do not require hardware at build time still open correctly.
- If certain plugins or DLLs are missing, see the **Troubleshooting** section.

---

## 4) Versioning & Reproducibility

- Ensure the app **version** is set in your build metadata inside `freeze_setup.py` (or a central version file). Tag releases in Git to keep artifacts traceable.
- Prefer pinned versions in `requirements.txt` for reproducible builds.
- Use consistent Python versions across dev and CI to avoid ABI mismatches.

---

## 5) Typical folder layout after successful builds

```
project-root/
├─ build/
│  ├─ AnycubicNFCTaggerQT5.app                   # (macOS) or under exe.macosx-*/...
│  └─ exe.win-amd64-3.12/AnycubicNFCTaggerQT5.exe  # (Windows) with needed DLLs
├─ dist/
│  ├─ AnycubicNFCTaggerQT5.dmg   # (macOS)
│  └─ AnycubicNFCTaggerQT5-<version>.msi   # (Windows, optional)
└─ packaging/
   └─ macos/
      └─ dmg_settings.py
```

---

## 6) Troubleshooting

### macOS
- **App won’t start / missing libraries**: Ensure `cx_Freeze` collected Qt plugins (platforms, imageformats). If not, add them via `include_files` in `freeze_setup.py` options.
- **DMG creation fails**: Verify `dmgbuild` is installed and that `packaging/macos/dmg_settings.py` exists. It must be able to locate the `.app` inside `build/`.
- **Gatekeeper warnings**: Unsigned apps will show warnings on first launch. Consider code signing and notarization for smoother distribution.

### Windows
- **DLL not found** at runtime: Add the missing DLL or Qt plugin directory to `include_files` in `freeze_setup.py` options.
- **App launches only on dev machine**: You likely depend on a system library missing on the target. Test on a clean VM and include the dependency in the build.
- **Antivirus flags the EXE**: Signing the executable and using a reputable installer (MSI) can reduce false positives.

### Cross-platform
- **Wrong Python/Qt build**: Mixing ARM64 vs x86_64 (or different Python minors) can break packaging. Build on the target platform/arch.
- **Paths with spaces**: Quote your paths or use short forms, especially in Windows PowerShell/CMD.

---

## 7) One-shot commands (quick reference)

### macOS
```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements.txt
python -m pip install cx-Freeze dmgbuild
rm -rf build dist
python freeze_setup.py build
mkdir -p dist
python -m dmgbuild -s packaging/macos/dmg_settings.py "AnycubicNFCTaggerQT5" dist/AnycubicNFCTaggerQT5.dmg
```

### Windows (PowerShell)
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements.txt
python -m pip install cx-Freeze dmgbuild
rmdir /s /q build dist 2>$null
python .\freeze_setup.py build
# optional:
python .\freeze_setup.py bdist_msi
```

---

**That’s it.** You should now have a runnable **DMG** for macOS and a standalone **EXE** (and optional **MSI**) for Windows.
