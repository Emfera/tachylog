#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# tachylog Feldstart
# Startet tachyflow (Web-UI) und tachylog (Collector) in einer Session.
#
# Voraussetzungen:
#   1. BT/TCP Bridge App läuft und hat TCP-Server auf localhost:4444 gestartet
#   2. pkg install nodejs python git (einmalig)
#   3. pip install git+https://github.com/Emfera/tachylog.git (einmalig)
#   4. cd ~/tachyflow && npm install && npm run build (einmalig)
#
# Verwendung:
#   bash start.sh [AUFNAHME] [SCHEMA] [EPSG]
#
#   AUFNAHME  Dateiname ohne Endung (Default: aufnahme_DATUM)
#   SCHEMA    gladiator2 | archsurv4qgis | free (Default: free)
#   EPSG      EPSG-Code   (Default: 31256 = MGI GK M31, Wien/NÖ)
#
# Beispiele:
#   bash start.sh
#   bash start.sh grabung_2026 gladiator2
#   bash start.sh grabung_2026 gladiator2 31256
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Widget-Modus ─────────────────────────────────────────────────────────────
# --widget: kein read, kein clear, termux-toast statt interaktiver Ausgabe.
WIDGET_MODE=0
FLOW_ONLY=0
ARGS=()
for arg in "$@"; do
    [[ "$arg" == "--widget" ]]    && WIDGET_MODE=1
    [[ "$arg" == "--flow-only" ]] && FLOW_ONLY=1
    [[ "$arg" != "--widget" && "$arg" != "--flow-only" ]] && ARGS+=("$arg")
done
set -- "${ARGS[@]+"${ARGS[@]}"}"

# ── Konfiguration ─────────────────────────────────────────────────────────────

TACHYFLOW_DIR="${TACHYFLOW_DIR:-$HOME/tachyflow}"
DATA_DIR="${DATA_DIR:-$HOME/tachylog-daten}"
BRIDGE_PORT="${BRIDGE_PORT:-tcp://localhost:4444}"
FLOW_PORT="${FLOW_PORT:-5000}"

DATE=$(date +%Y-%m-%d)
AUFNAHME="${1:-aufnahme_$DATE}"
SCHEMA_ARG="${2:-free}"
EPSG="${3:-31256}"

# ── Farben (Termux unterstützt ANSI) ─────────────────────────────────────────

R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;36m'; N='\033[0m'
BOLD='\033[1m'

banner() { echo -e "\n${BOLD}${B}  $*${N}"; }
ok()     { echo -e "  ${G}✓${N}  $*"; }
warn()   { echo -e "  ${Y}⚠${N}  $*"; }
err()    { echo -e "  ${R}✗${N}  $*"; }
info()   { echo -e "     $*"; }
toast()  {
    if [[ $WIDGET_MODE -eq 1 ]] && command -v termux-toast &>/dev/null; then
        termux-toast -s "$*"
    else
        echo -e "  ★  $*"
    fi
}

# ── Aufräumen beim Beenden ────────────────────────────────────────────────────

FLOW_PID=""
cleanup() {
    echo ""
    banner "Beende..."
    if [[ -n "$FLOW_PID" ]] && kill -0 "$FLOW_PID" 2>/dev/null; then
        kill "$FLOW_PID" 2>/dev/null
        ok "tachyflow beendet"
    fi
    echo ""
    echo -e "  ${BOLD}Daten gespeichert in:${N}"
    for f in "$DATA_DIR/$AUFNAHME".*; do
        [[ -f "$f" ]] && info "$(basename "$f")  →  $f"
    done
    echo ""
}
trap cleanup EXIT INT TERM

# ── Header ────────────────────────────────────────────────────────────────────

[[ $WIDGET_MODE -eq 0 ]] && clear
echo ""
echo -e "  ${BOLD}╔══════════════════════════════════════╗${N}"
echo -e "  ${BOLD}║        tachylog  Feldstart           ║${N}"
echo -e "  ${BOLD}╚══════════════════════════════════════╝${N}"
echo ""
info "Aufnahme : ${BOLD}$AUFNAHME${N}"
info "Schema   : ${BOLD}$SCHEMA_ARG${N}"
info "EPSG     : ${BOLD}$EPSG${N}"
info "Daten    : ${BOLD}$DATA_DIR${N}"
echo ""

# ── Verzeichnis anlegen ───────────────────────────────────────────────────────

mkdir -p "$DATA_DIR"

# ── Voraussetzungen prüfen ────────────────────────────────────────────────────

banner "Prüfe Voraussetzungen..."

# Python / tachylog
if ! command -v tachylog &>/dev/null; then
    err "tachylog nicht gefunden."
    info "Installieren mit:  pip install git+https://github.com/Emfera/tachylog.git"
    exit 1
fi
ok "tachylog $(tachylog --version 2>/dev/null || echo '(Version unbekannt)')"

# Node.js / tachyflow
if ! command -v node &>/dev/null; then
    err "Node.js nicht gefunden."
    info "Installieren mit:  pkg install nodejs"
    exit 1
fi
ok "Node.js $(node --version)"

# tachyflow Build
FLOW_BUNDLE="$TACHYFLOW_DIR/dist/index.cjs"
if [[ ! -f "$FLOW_BUNDLE" ]]; then
    warn "tachyflow Build nicht gefunden — baue jetzt..."
    info "(Einmalig, dauert ~1 Minute)"
    if [[ ! -d "$TACHYFLOW_DIR" ]]; then
        err "tachyflow-Verzeichnis nicht gefunden: $TACHYFLOW_DIR"
        info "Klonen mit:  git clone https://github.com/Emfera/tachyflow.git ~/tachyflow"
        exit 1
    fi
    (cd "$TACHYFLOW_DIR" && npm install --silent && npm run build) \
        && ok "Build erfolgreich" \
        || { err "Build fehlgeschlagen"; exit 1; }
fi

# BT/TCP Bridge
echo ""
warn "BT/TCP Bridge prüfen:"
info "→ Ist die App gestartet und mit dem TS07 verbunden?"
info "→ Ist der TCP-Server auf localhost:4444 aktiv?"
if [[ $WIDGET_MODE -eq 0 ]]; then
    echo ""
    echo -ne "  Weiter mit Enter (oder Ctrl+C zum Abbrechen)... "
    read -r
fi

# Verbindung testen
if command -v nc &>/dev/null; then
    if nc -z localhost 4444 2>/dev/null; then
        ok "Verbindung zu localhost:4444 OK"
    else
        warn "localhost:4444 nicht erreichbar — tachylog verbindet automatisch"
        toast "⚠ Port 4444 nicht erreichbar — tachylog versucht Verbindung"
        if [[ $WIDGET_MODE -eq 0 ]]; then
            echo -ne "  Weiter mit Enter... "
            read -r
        fi
    fi
fi

# ── Schema-Pfad auflösen ──────────────────────────────────────────────────────

# Entweder built-in Schema-Name oder direkter Dateipfad
TACHYLOG_SCHEMAS=$(python3 -c "import tachylog, os; print(os.path.join(os.path.dirname(tachylog.__file__), 'schemas'))" 2>/dev/null || echo "")

if [[ "$SCHEMA_ARG" == "free" ]]; then
    SCHEMA_OPT=""
elif [[ -f "$SCHEMA_ARG" ]]; then
    SCHEMA_OPT="--schema $SCHEMA_ARG"
elif [[ -n "$TACHYLOG_SCHEMAS" && -f "$TACHYLOG_SCHEMAS/${SCHEMA_ARG}.json" ]]; then
    SCHEMA_OPT="--schema $TACHYLOG_SCHEMAS/${SCHEMA_ARG}.json"
else
    warn "Schema '$SCHEMA_ARG' nicht gefunden — starte ohne Schema"
    SCHEMA_OPT=""
fi

# ── tachyflow starten ─────────────────────────────────────────────────────────

banner "Starte tachyflow (Web-UI)..."

PORT=$FLOW_PORT NODE_ENV=production \
    node "$FLOW_BUNDLE" >> "$DATA_DIR/tachyflow.log" 2>&1 &
FLOW_PID=$!

# Warten bis Server antwortet (max. 10s)
for i in $(seq 1 20); do
    sleep 0.5
    if kill -0 "$FLOW_PID" 2>/dev/null && \
       (echo > /dev/tcp/localhost/$FLOW_PORT) 2>/dev/null; then
        ok "tachyflow läuft auf http://localhost:$FLOW_PORT"
        if [[ $WIDGET_MODE -eq 1 ]]; then
            am start -a android.intent.action.VIEW \
                -d "http://localhost:$FLOW_PORT" 2>/dev/null || true
            toast "tachylog gestartet — Browser geöffnet"
        fi
        break
    fi
    if ! kill -0 "$FLOW_PID" 2>/dev/null; then
        err "tachyflow konnte nicht gestartet werden"
        info "Log: $DATA_DIR/tachyflow.log"
        tail -5 "$DATA_DIR/tachyflow.log" 2>/dev/null | sed 's/^/     /'
        exit 1
    fi
    [[ $i -eq 20 ]] && warn "tachyflow antwortet noch nicht — Log: $DATA_DIR/tachyflow.log"
done

info "Browser öffnen:  http://localhost:$FLOW_PORT"

# ── tachylog starten (optional) ─────────────────────────────────────────────

if [[ $FLOW_ONLY -eq 1 ]]; then
    banner "Nur tachyflow — warte auf Ctrl+C"
    echo ""
    info "tachylog läuft nicht — Verbindung gehört tachyflow."
    echo -e "  ${Y}Beenden: Ctrl+C${N}"
    echo ""
    # Vordergrund blockieren bis Ctrl+C
    while kill -0 "$FLOW_PID" 2>/dev/null; do sleep 2; done
else
    banner "Starte tachylog..."
    echo ""
    echo -e "  ${BOLD}Ausgabedateien:${N}"
    info "SQLite  →  $DATA_DIR/$AUFNAHME.db"
    info "CSV     →  $DATA_DIR/$AUFNAHME.csv"
    info "GeoJSON →  $DATA_DIR/$AUFNAHME.geojson"
    echo ""
    echo -e "  ${Y}Beenden: Ctrl+C${N}"
    echo ""
    # tachylog läuft im Vordergrund (Ctrl+C beendet alles via trap)
    tachylog collect \
        --port "$BRIDGE_PORT" \
        --db      "$DATA_DIR/$AUFNAHME.db" \
        --csv     "$DATA_DIR/$AUFNAHME.csv" \
        --geojson "$DATA_DIR/$AUFNAHME.geojson" \
        --epsg    "$EPSG" \
        ${SCHEMA_OPT}
fi
