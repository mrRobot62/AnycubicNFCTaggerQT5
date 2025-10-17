# freeze_setup.py
import sys
from cx_Freeze import setup, Executable

# Dateien/Ordner, die ins Bundle müssen
include_files = [
    ("src/anycubic_nfc_qt5/config/ac_filaments.ini", "anycubic_nfc_qt5/config/ac_filaments.ini"),
    ("src/anycubic_nfc_qt5/ui/resources", "anycubic_nfc_qt5/ui/resources"),
]

build_exe_options = dict(
    excludes=["tkinter", "tests"],
    includes=["PyQt5", "smartcard"],
    packages=["os", "sys", "anycubic_nfc_qt5"],
    include_files=include_files,
    optimize=1,
)

# inside setup(..., options={"bdist_mac": {...}})
bdist_mac_options = {
    "bundle_name": "AnycubicNFCTaggerQT5",
    "iconfile": "packaging/macos/app.icns",  # adjust if needed
    "custom_info_plist": {
        "CFBundleIdentifier": "com.yourorg.anycubicnfctaggerqt5",
        "CFBundleDisplayName": "AnycubicNFCTaggerQT5",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
}

base = "gui" if sys.platform == "darwin" else None

executables = [
    Executable(
        script="AnycubicNFCTaggerQT5.py",
        target_name="AnycubicNFCTaggerQT5",
        base=base,
        icon="packaging/macos/app.icns",  # optional; kannst du weglassen, wenn nicht vorhanden
    )
]

setup(
    name="AnycubicNFCTaggerQT5",
    version="0.1.0",
    description="PyQt5 GUI for Anycubic NFC filament tagging",
    options={"build_exe": build_exe_options},
    executables=executables,
)