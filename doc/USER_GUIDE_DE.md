# Benutzerhandbuch (Deutsch)

Dieses Handbuch erklärt, wie man **AnycubicNFCTaggerQT5** verwendet, um NFC-Filament-Tags zu lesen, zu bearbeiten und zu schreiben.

---

## 1) Start der Anwendung

- **macOS**: Öffne `AnycubicNFCTaggerQT5.app` (aus `/Applications` oder nach DMG-Kopie).
- **Windows**: Doppelklicke auf `AnycubicNFCTaggerQT5.exe`.

Nach dem Start sucht die Anwendung automatisch nach einem angeschlossenen NFC-Lesegerät.

---

## 2) Erste Bildschirme

### Kein NFC-Reader gefunden
Wenn kein Lesegerät erkannt wird, erscheint:
> „No NFC-Reader found“

Überprüfe USB-Verbindung und Treiber, starte dann die App neu.

### Reader erkannt, kein Tag vorhanden
Wenn der Reader erkannt wird, aber kein Tag aufgelegt ist, wartet die Anwendung auf einen NFC-Tag.

---

## 3) Tag lesen

1. Lege einen Anycubic-NFC-Tag auf das Lesegerät.  
2. Die Speicherseiten (z. B. 0x00–0x2C) werden ausgelesen und im **Page Editor Dock** angezeigt.  
3. Bekannte Felder (z. B. Filamentname, Farbe) werden mit verständlichen Namen angezeigt.

---

## 4) Tag-Daten bearbeiten

Im **Page Editor Dock** kannst du:

- Hex-Werte (`B0–B3`) direkt ändern.  
- ASCII-Text in das Feld eingeben (automatische Synchronisierung).  
- Für die Farbseite (`0x20`) kann ein Farbwert im Format `#RRGGBBAA` (z. B. `#FF8000FF`) eingegeben werden.

Markiere die gewünschten Seiten mit der Checkbox **Apply**, um sie für das Schreiben vorzubereiten.

---

## 5) Änderungen auf den Tag schreiben

Klicke auf **WRITE NFC**:  
- Nur markierte Seiten werden geschrieben.  
- Das Log-Fenster zeigt Erfolg oder Fehlermeldungen an.

> Tipp: Nach dem Schreiben den Tag erneut lesen, um die Daten zu überprüfen.

---

## 6) Simulation und Löschen

- **SIMULATE**: Zeigt alle Seitendaten im Log an (keine Schreibvorgänge).  
- **CLEAR**: Setzt alle Felder auf `00 00 00 00` zurück und löscht verbundene UI-Auswahlen.

---

## 7) Benutzerbereich löschen

1. Klicke **DELETE (User Area)**.  
2. Bestätige mit `RESET`.  
3. Der Benutzerbereich wird vollständig gelöscht.

> ⚠️ Dieser Vorgang kann nicht rückgängig gemacht werden!

---

## 8) Empfohlener Arbeitsablauf

1. Tag einlegen und Daten prüfen.  
2. „Mark Known Fields“ klicken, um relevante Felder automatisch zu markieren.  
3. Änderungen durchführen.  
4. **WRITE NFC** klicken.  
5. Tag erneut lesen und prüfen.

---

## 9) Fehlerbehebung

| Problem | Ursache | Lösung |
|----------|----------|--------|
| Kein Reader erkannt | USB oder Treiberproblem | Treiber neu installieren |
| Schreibfehler | Tag gesperrt | Anderen Tag verwenden |
| Farben/Text falsch | Falsches Format | Nur ASCII oder `#RRGGBBAA` verwenden |
| GUI unvollständig | Fehlende Ressourcen | Neu installieren |

---

**Ende des Benutzerhandbuchs**
