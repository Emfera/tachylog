#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Termux:Widget Shortcut — tachylog Feldstart
#
# Dieses Skript gehört in ~/.shortcuts/tachylog.sh
# Es wird vom Termux:Widget Home-Screen-Button aufgerufen.
#
# Einrichtung (einmalig):
#   bash ~/tachylog/setup-widget.sh
# ─────────────────────────────────────────────────────────────────────────────

# Wo liegt start.sh?  Konfigurierbar via Umgebungsvariable TACHYLOG_DIR.
TACHYLOG_DIR="${TACHYLOG_DIR:-$HOME/tachylog}"
START_SCRIPT="$TACHYLOG_DIR/start.sh"

# Konfiguration — hier anpassen oder per Umgebungsvariable überschreiben
AUFNAHME="${TACHYLOG_AUFNAHME:-aufnahme_$(date +%Y-%m-%d)}"
SCHEMA="${TACHYLOG_SCHEMA:-free}"          # free | gladiator2 | archsurv4qgis
EPSG="${TACHYLOG_EPSG:-31256}"             # 31256=M31, 31255=M28, 31257=M34

# ── Skript prüfen ─────────────────────────────────────────────────────────────
if [[ ! -f "$START_SCRIPT" ]]; then
    if command -v termux-toast &>/dev/null; then
        termux-toast -s "✗ start.sh nicht gefunden: $START_SCRIPT"
    fi
    exit 1
fi

# ── Starten ───────────────────────────────────────────────────────────────────
# --widget:     überspringt interaktive Prompts, öffnet Browser automatisch
# --flow-only:  startet nur tachyflow, kein tachylog (empfohlen — BT/TCP Bridge
#               erlaubt nur eine Verbindung gleichzeitig)
exec bash "$START_SCRIPT" "$AUFNAHME" "$SCHEMA" "$EPSG" --widget --flow-only
