# Installationsanleitung (Deutsch)

Dieses Dokument beschreibt, wie man eine Entwicklungsumgebung für **AnycubicNFCTaggerQT5** (v0.3.0) auf macOS und Windows einrichtet
und die Anwendung aus dem Quellcode startet.

> Quellcode und Kommentare sind in **Englisch** geschrieben; diese Anleitung ist auf **Deutsch** für Benutzerfreundlichkeit.

---

## 1) Voraussetzungen

- **Python**: Empfohlen wird Version 3.12.x
- **Git** (optional, wenn das Repository geklont wird)
- **Qt / PyQt5**: Wird automatisch über `pip` installiert (ist in `pyproject.toml` als Abhängigkeit definiert)
- **NFC (pyscard)**: Abhängigkeit wird automatisch installiert; falls der Build fehlschlägt, bitte pyscard-Dokumentation zu PC/SC-Treibern konsultieren

---

## 2) Virtuelle Umgebung erstellen und aktivieren

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

## 3) Abhängigkeiten installieren

```bash
python -m pip install --upgrade pip wheel setuptools
python -m pip install -e .
```

> Wenn du kein Entwicklungs-Setup möchtest, kannst du die Abhängigkeiten direkt installieren:
> ```bash
> python -m pip install "PyQt5>=5.15,<6" "pyscard>=2.0"
> ```

---

## 4) Anwendung aus dem Quellcode starten

```bash
python -m anycubic_nfc_qt5.app
# oder
python src/anycubic_nfc_qt5/app.py
```

Wenn das GUI startet, ist die Entwicklungsumgebung erfolgreich eingerichtet.

---

## 5) Nächste Schritte

- Siehe **BUILDING-BINARIES_DE.md**, um ausführbare Dateien (DMG/EXE) zu erstellen.
- Siehe **USER_GUIDE_DE.md**, um die Anwendung zu bedienen.
