#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Termux:Widget Einrichtung (einmalig)
#
# Richtet den Home-Screen-Button für tachylog ein:
#   1. ~/.shortcuts/ Verzeichnis mit korrekten Permissions anlegen
#   2. tachylog.sh in ~/.shortcuts/ kopieren und ausführbar machen
#   3. Pinned Shortcut auf dem Home-Screen anbieten
#
# Aufruf:
#   bash ~/tachylog/setup-widget.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; N='\033[0m'; BOLD='\033[1m'
ok()   { echo -e "  ${G}✓${N}  $*"; }
err()  { echo -e "  ${R}✗${N}  $*"; }
warn() { echo -e "  ${Y}⚠${N}  $*"; }
info() { echo -e "     $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "  ${BOLD}Termux:Widget Einrichtung${N}"
echo ""

# ── 1. ~/.shortcuts anlegen ───────────────────────────────────────────────────
SHORTCUTS="$HOME/.shortcuts"
mkdir -p "$SHORTCUTS"
# Termux:Widget erfordert exakt 700 auf dem Verzeichnis
chmod 700 "$SHORTCUTS"
ok "~/.shortcuts angelegt (chmod 700)"

# ── 2. tachylog.sh kopieren ───────────────────────────────────────────────────
SRC="$SCRIPT_DIR/tachylog.sh"
DST="$SHORTCUTS/tachylog.sh"

if [[ ! -f "$SRC" ]]; then
    err "tachylog.sh nicht gefunden: $SRC"
    exit 1
fi

cp "$SRC" "$DST"
chmod +x "$DST"
ok "tachylog.sh → $DST (chmod +x)"

# ── 3. TACHYLOG_DIR in tachylog.sh eintragen ─────────────────────────────────
# Ersetzt den Platzhalter-Pfad durch den tatsächlichen Installationspfad
sed -i "s|TACHYLOG_DIR=\"\${TACHYLOG_DIR:-\$HOME/tachylog}\"|TACHYLOG_DIR=\"\${TACHYLOG_DIR:-$SCRIPT_DIR}\"|" "$DST"
ok "Installationspfad eingetragen: $SCRIPT_DIR"

# ── 4. Termux:Widget Verfügbarkeit prüfen ─────────────────────────────────────
echo ""
if command -v termux-toast &>/dev/null; then
    ok "Termux:API verfügbar (termux-toast)"
else
    warn "Termux:API nicht installiert"
    info "Installieren für Toast-Benachrichtigungen: pkg install termux-api"
    info "(Optional — tachylog funktioniert auch ohne)"
fi

# ── 5. Pinned Shortcut anbieten ───────────────────────────────────────────────
echo ""
echo -e "  ${BOLD}Nächste Schritte:${N}"
echo ""
info "A) Termux:Widget als Widget auf den Home-Screen ziehen:"
info "   Home-Screen → Widgets → Termux:Widget → tachylog.sh auswählen"
echo ""
info "   ODER"
echo ""
info "B) Direkten Home-Screen-Button erstellen (Termux:Widget ≥ 0.13):"

# Pinned Shortcut via Activity — funktioniert auf Android 8+
if command -v am &>/dev/null; then
    echo ""
    echo -ne "  Pinned-Shortcut-Dialog jetzt öffnen? [J/n] "
    read -r ANTWORT
    if [[ "${ANTWORT:-J}" =~ ^[Jj]$ ]]; then
        am start \
            com.termux.widget/com.termux.widget.TermuxCreateShortcutActivity \
            2>/dev/null \
            && ok "Shortcut-Dialog geöffnet — tachylog.sh auswählen" \
            || warn "Konnte Dialog nicht öffnen — bitte manuell via Widgets hinzufügen"
    fi
fi

echo ""
ok "Einrichtung abgeschlossen."
info "Shortcut startet: bash $DST"
echo ""
