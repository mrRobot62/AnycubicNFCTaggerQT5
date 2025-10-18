# freeze_setup.py
# Cross-platform cx_Freeze setup for Windows (.exe) and macOS (.app)
# Code and comments intentionally in English.

from cx_Freeze import setup, Executable
from pathlib import Path
import sys

APP_NAME = "AnycubicNFCTaggerQT5"
VERSION = "0.3.0"
BASE_DIR = Path(__file__).parent

# Common build options
build_exe_options = {
    "includes": [
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "json",
        "logging",
        "pathlib",
        # --- smartcard (pyscard) ---
        "smartcard",
        "smartcard.Exceptions",
        "smartcard.System",
        "smartcard.scard",
        "smartcard.CardMonitoring",
        "smartcard.CardType",
        "smartcard.util",
    ],
    "excludes": [
        # removed "smartcard" from excludes, because the app imports it
        "tkinter",
        "unittest",
        "tests",
    ],
    "zip_include_packages": ["encodings", "importlib", "PyQt5"],
    "zip_exclude_packages": [],
    "optimize": 1,
    "silent_level": 1,
}

# Include resources (adjust folder names if needed)
resources = []
for pat in ["resources", "assets", "icons"]:
    p = BASE_DIR / pat
    if p.exists():
        # keep folder structure
        resources.append((str(p), str(p)))
build_exe_options["include_files"] = resources

# Platform-specific executable base and icon
if sys.platform == "win32":
    base = "Win32GUI"
    icon = BASE_DIR / "packaging" / "windows" / "app.ico"
    target_name = f"{APP_NAME}.exe"
else:
    base = None  # GUI apps on macOS don't need a special base
    icon = BASE_DIR / "packaging" / "macos" / "app.icns"
    target_name = APP_NAME  # target inside the .app bundle

executables = [
    Executable(
        script="app.py",          # <-- Adjust if your entry point has a different name
        base=base,
        target_name=target_name,
        icon=str(icon) if icon.exists() else None,
    )
]

# macOS bundle options for 'bdist_mac'
bdist_mac_options = {
    "bundle_name": APP_NAME,
    # dmgbuild will handle the DMG; this is just the .app packaging
    "iconfile": str(icon) if icon.exists() else None,
}

setup(
    name=APP_NAME,
    version=VERSION,
    description="PyQt5 tool for Anycubic NFC filament tags",
    options={
        "build_exe": build_exe_options,
        "bdist_mac": bdist_mac_options,
    },
    executables=executables,
)
