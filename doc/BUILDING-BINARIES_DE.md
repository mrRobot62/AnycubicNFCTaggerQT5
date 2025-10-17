# Erstellen von Binaries (macOS DMG & Windows EXE)

Diese Anleitung beschreibt, wie aus dem Projekt **AnycubicNFCTaggerQT5** ausführbare Dateien für macOS und Windows erzeugt werden.

---

## 1) Voraussetzungen

- **Python 3.12.x** (empfohlen)
- Abhängigkeiten installieren:
  ```bash
  python -m pip install -r requirements.txt
  python -m pip install cx-Freeze dmgbuild
  ```

---

## 2) macOS: App-Bundle und DMG-Datei erstellen

### 2.1 `.app` mit cx_Freeze erzeugen

```bash
rm -rf build dist
python freeze_setup.py build
```

Die erzeugte App befindet sich üblicherweise in:
```
build/AnycubicNFCTaggerQT5.app
```

### 2.2 `.dmg` mit dmgbuild erzeugen

```bash
mkdir -p dist
python -m dmgbuild -s packaging/macos/dmg_settings.py "AnycubicNFCTaggerQT5" dist/AnycubicNFCTaggerQT5.dmg
```

Die Datei `AnycubicNFCTaggerQT5.dmg` befindet sich danach im Ordner `dist/`.

---

## 3) Windows: EXE (und optional MSI) erzeugen

```powershell
rmdir /s /q build dist 2>$null
python .\freeze_setup.py build
```

Das Ergebnis liegt in:
```
build\exe.win-amd64-3.12\AnycubicNFCTaggerQT5.exe
```

Optional kann eine MSI-Datei erstellt werden:
```powershell
python .\freeze_setup.py bdist_msi
```

---

## 4) Typische Struktur nach erfolgreichem Build

```
project-root/
├─ build/
│  ├─ AnycubicNFCTaggerQT5.app
│  └─ exe.win-amd64-3.12/AnycubicNFCTaggerQT5.exe
├─ dist/
│  ├─ AnycubicNFCTaggerQT5.dmg
│  └─ AnycubicNFCTaggerQT5-<version>.msi
└─ packaging/macos/dmg_settings.py
```

---

## 5) Häufige Probleme

| Problem | Ursache | Lösung |
|----------|----------|--------|
| Fehlende Qt-Plugins | cx_Freeze hat Plugins nicht kopiert | In `freeze_setup.py` über `include_files` hinzufügen |
| DMG-Build schlägt fehl | dmgbuild nicht installiert oder Pfade fehlerhaft | dmgbuild installieren und Pfade prüfen |
| Unsigned App-Warnung | Keine Code-Signatur | Siehe **PACKAGING_SIGNING_DE.md** für Signierungsschritte |

---

**Fertig – Die ausführbare DMG/EXE-Datei kann nun verteilt werden.**
