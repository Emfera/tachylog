#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# tachylog + tachyflow Einrichtung für Android/Termux
#
# Aufruf (einmalig):
#   curl -fsSL https://raw.githubusercontent.com/Emfera/tachylog/main/setup-termux.sh | bash
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Farben ────────────────────────────────────────────────────────────────────
G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; B='\033[0;36m'
BOLD='\033[1m'; N='\033[0m'

step()  { echo -e "\n${BOLD}${B}▶  $*${N}"; }
ok()    { echo -e "   ${G}✓  $*${N}"; }
err()   { echo -e "\n   ${R}✗  FEHLER: $*${N}\n"; exit 1; }
info()  { echo -e "   $*"; }

# ── Hilfsfunktion: Befehl mit Fehlerausgabe ausführen ─────────────────────────
run() {
    # Führt einen Befehl aus. Bei Fehler: vollständige Ausgabe + Abbruch.
    local label="$1"; shift
    local tmpfile
    tmpfile=$(mktemp)

    info "$ $*"
    if "$@" > "$tmpfile" 2>&1; then
        ok "$label"
        rm -f "$tmpfile"
    else
        echo -e "\n   ${R}Ausgabe:${N}"
        sed 's/^/   /' "$tmpfile"
        rm -f "$tmpfile"
        err "$label fehlgeschlagen"
    fi
}

# ── Header ────────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "  ${BOLD}╔══════════════════════════════════════╗${N}"
echo -e "  ${BOLD}║   tachylog + tachyflow  Setup        ║${N}"
echo -e "  ${BOLD}╚══════════════════════════════════════╝${N}"
echo ""
info "Installiert: tachylog 1.1.0, tachyflow (aktuell)"
info "Zielordner:  ~/tachylog  ~/tachyflow"
echo ""
echo -ne "  Weiter mit Enter, Abbrechen mit Ctrl+C... "
read -r

# ── 1. Pakete aktualisieren ───────────────────────────────────────────────────
step "1/7  Termux-Pakete aktualisieren"
run "pkg update"   pkg update -y
run "pkg upgrade"  pkg upgrade -y

# ── 2. Abhängigkeiten installieren ────────────────────────────────────────────
step "2/7  Abhängigkeiten installieren (python, git, nodejs)"
run "pkg install"  pkg install -y python git nodejs

# ── 3. tachylog installieren ─────────────────────────────────────────────────
step "3/7  tachylog installieren"
run "pip install"  pip install --upgrade \
    git+https://github.com/Emfera/tachylog.git

# Schnelltest
info "Teste tachylog..."
if tachylog --help > /dev/null 2>&1; then
    VERSION=$(python3 -c "import tachylog; print(tachylog.__version__)" 2>/dev/null || echo "?")
    ok "tachylog $VERSION verfügbar"
else
    err "tachylog --help schlug fehl"
fi

# ── 4. tachyflow klonen ───────────────────────────────────────────────────────
step "4/7  tachyflow klonen"
if [[ -d "$HOME/tachyflow" ]]; then
    info "Alte Version gefunden — wird gelöscht"
    run "rm -rf ~/tachyflow"  rm -rf "$HOME/tachyflow"
fi
run "git clone tachyflow"  git clone \
    https://github.com/Emfera/tachyflow.git \
    "$HOME/tachyflow"

# ── 5. tachyflow bauen ────────────────────────────────────────────────────────
step "5/7  tachyflow bauen (npm install + build, ~2–3 Minuten)"
cd "$HOME/tachyflow"
run "npm install"   npm install --prefer-offline
run "npm run build" npm run build
cd "$HOME"

# ── 6. Startskripte (tachylog-Repo klonen) ───────────────────────────────────
step "6/7  Startskripte holen"
if [[ -d "$HOME/tachylog" ]]; then
    info "~/tachylog bereits vorhanden — aktualisiere"
    run "git pull tachylog"  git -C "$HOME/tachylog" pull --ff-only
else
    run "git clone tachylog-repo"  git clone \
        https://github.com/Emfera/tachylog.git \
        "$HOME/tachylog"
fi
chmod +x "$HOME/tachylog/start.sh" \
         "$HOME/tachylog/setup-widget.sh" \
         "$HOME/tachylog/tachylog.sh"
ok "Skripte ausführbar"

# ── 7. Termux:Widget einrichten ───────────────────────────────────────────────
step "7/7  Termux:Widget einrichten"
if [[ ! -f /data/data/com.termux.widget/files/app.info \
   && ! -d /data/data/com.termux.widget ]]; then
    echo ""
    echo -e "   ${Y}⚠  Termux:Widget nicht installiert.${N}"
    info "Bitte jetzt aus F-Droid installieren:"
    info "https://f-droid.org/packages/com.termux.widget/"
    echo ""
    echo -ne "   Nach der Installation Enter drücken (oder Ctrl+C überspringen)... "
    read -r
fi
bash "$HOME/tachylog/setup-widget.sh"

# ── Fertig ────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}${G}╔══════════════════════════════════════╗${N}"
echo -e "  ${BOLD}${G}║   Einrichtung abgeschlossen ✓        ║${N}"
echo -e "  ${BOLD}${G}╚══════════════════════════════════════╝${N}"
echo ""
info "Feldstart ab jetzt:"
echo ""
info "  ${BOLD}Option A${N}  Home-Screen-Button  →  tachylog.sh tippen"
info "  ${BOLD}Option B${N}  bash ~/tachylog/start.sh"
echo ""
info "Daten landen in:  ~/tachylog-daten/"
echo ""
