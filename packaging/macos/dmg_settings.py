# packaging/macos/dmg_settings.py
# Settings for dmgbuild. Run your app build first (freeze_setup.py build or bdist_mac).

import os

# Name des gemounteten Volumes (frei wählbar)
volume_name = "AnycubicNFCTaggerQT5"
# Komprimiertes DMG
format = "UDZO"

# Finder-Fenster Layout
window_rect = ((200, 200), (540, 380))
default_view = "icon-view"
icon_size = 128
text_size = 12

# Optionales Hintergrundbild (PNG) – bei Bedarf auskommentieren
# background = "packaging/macos/dmg_background.png"

# /Applications Symlink
symlinks = {"Applications": "/Applications"}

# ---- .app finden/übernehmen ----
# Du kannst beim Aufruf explizit einen Pfad setzen:
#   -D APP_PATH="build/anycubicnfctaggerqt5-0.1.0.app"
APP_PATH = globals().get("APP_PATH")

def _find_app_under_build():
    # 1) bdist_mac-Variante (z. B. anycubicnfctaggerqt5-0.1.0.app)
    for entry in os.listdir("build"):
        if entry.endswith(".app"):
            return os.path.join("build", entry)
    # 2) klassische build-Struktur (exe.macosx-*/<Name>.app)
    for root, dirs, _ in os.walk("build"):
        for d in dirs:
            if d.endswith(".app"):
                return os.path.join(root, d)
    raise FileNotFoundError(
        "No .app found under 'build/'. Build first with:\n"
        "  python freeze_setup.py build\n"
        "oder\n"
        "  python freeze_setup.py bdist_mac"
    )

if not APP_PATH:
    APP_PATH = _find_app_under_build()

APP_NAME = os.path.basename(APP_PATH)

# Inhalte des DMG: (Quelle, Zielname im DMG)
files = [(APP_PATH, APP_NAME)]

# Icon-Positionen (Namen müssen mit den Zielnamen und Symlink-Keys übereinstimmen)
icon_locations = {
    APP_NAME: (140, 200),
    "Applications": (400, 200),
}