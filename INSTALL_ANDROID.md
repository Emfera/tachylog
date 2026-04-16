# Android-Einrichtung (Termux)

Einmalige Einrichtung — danach reicht `bash start.sh`.

---

## 1. Apps installieren

| App | Quelle | Zweck |
|---|---|---|
| **Termux** | [F-Droid](https://f-droid.org/packages/com.termux/) | Linux-Terminal |
| **BT/TCP Bridge** | Play Store (Marek Masár) | Bluetooth → TCP |

> Termux unbedingt von **F-Droid** installieren, nicht aus dem Play Store (veraltete Version).

---

## 2. Termux einrichten

```bash
pkg update && pkg upgrade -y
pkg install -y python git nodejs openssh
```

---

## 3. tachylog installieren

```bash
pip install git+https://github.com/Emfera/tachylog.git
```

Testen:
```bash
tachylog --help
```

---

## 4. tachyflow einrichten

```bash
git clone https://github.com/Emfera/tachyflow.git ~/tachyflow
cd ~/tachyflow
npm install
npm run build
```

---

## 5. Startskript herunterladen

```bash
curl -o ~/start.sh \
  https://raw.githubusercontent.com/Emfera/tachylog/main/start.sh
chmod +x ~/start.sh
```

---

## 6. TS07 einstellen

Am Instrument:

```
Daten → Ausgabe → Interface
  Protokoll : GSI
  Format    : GSI16
  Maske     : Maske 1
```

---

## 7. BT/TCP Bridge konfigurieren

1. App öffnen
2. **Paired Devices** → TS07 auswählen → verbinden
3. **TCP Server** → Port `4444` → **Start**

---

## 6. Home-Screen-Button (Termux:Widget)

Einmalig nach der Installation:

```bash
# Termux:Widget aus F-Droid installieren (App, nicht Terminal-Befehl)
# Dann in Termux:
bash ~/tachylog/setup-widget.sh
```

Das Skript:
- legt `~/.shortcuts/` mit den richtigen Permissions an
- kopiert `tachylog.sh` dorthin
- bietet an, den Pinned-Shortcut-Dialog direkt zu öffnen

**Widget auf Home-Screen ziehen:**
Home-Screen lang drücken → Widgets → Termux:Widget → `tachylog.sh` auswählen

**Direkter Icon-Button** (empfohlen):
Home-Screen lang drücken → Widgets → Termux:Shortcut → `tachylog.sh` auswählen

Ein Tipp auf den Button startet den gesamten Stack:
tachyflow startet im Hintergrund, Browser öffnet sich auf `http://localhost:5000`,
tachylog läuft im Terminal und sammelt Messungen.

**Konfiguration** (oben in `~/.shortcuts/tachylog.sh` anpassen):
```bash
AUFNAHME="grabung_2026"      # Fixer Dateiname statt Datum
SCHEMA="gladiator2"          # Schema für PID-Validierung
EPSG="31256"                 # Koordinatensystem
```

---

## Feldstart (täglich)

```bash
# Einfachster Start (freies PID-Format, EPSG 31256)
bash ~/start.sh

# Mit Gladiator_2 Schema und Dateiname
bash ~/start.sh grabung_2026-04-16 gladiator2

# Anderes Koordinatensystem (M28, Westösterreich)
bash ~/start.sh grabung_2026-04-16 gladiator2 31255
```

Reihenfolge:
1. BT/TCP Bridge → TS07 verbinden → TCP-Server starten
2. `bash ~/start.sh` in Termux
3. Browser auf `http://localhost:5000` öffnen (tachyflow)
4. Am TS07 messen

`Ctrl+C` beendet alles sauber.

---

## Datenablage

Alle Ausgabedateien landen in `~/tachylog-daten/`:

```
~/tachylog-daten/
  aufnahme_2026-04-16.db       ← SQLite (Rohdaten)
  aufnahme_2026-04-16.csv      ← CSV (Emlid Flow kompatibel)
  aufnahme_2026-04-16.geojson  ← GeoJSON mit CRS-Tag
  tachyflow.log                ← Web-UI Log
```

---

## Daten auf Desktop übertragen

Per USB (empfohlen):
```bash
# Am Desktop
adb pull /data/data/com.termux/files/home/tachylog-daten/ .
```

Per SSH über WLAN:
```bash
# In Termux
sshd
# Am Desktop
scp -P 8022 user@<IP>:~/tachylog-daten/* .
```
