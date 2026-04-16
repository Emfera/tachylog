#!/data/data/com.termux/files/usr/bin/bash
# Nur tachyflow starten — kein tachylog, eine einzige TCP-Verbindung
FLOW_DIR="${HOME}/tachyflow"
FLOW_LOG="${HOME}/tachylog-daten/tachyflow.log"
FLOW_PORT=5000

mkdir -p "${HOME}/tachylog-daten"

# tachyflow starten
PORT=$FLOW_PORT NODE_ENV=production \
    node "$FLOW_DIR/dist/index.cjs" >> "$FLOW_LOG" 2>&1 &
FLOW_PID=$!

# Warten bis bereit
for i in $(seq 1 20); do
    sleep 0.5
    (echo > /dev/tcp/localhost/$FLOW_PORT) 2>/dev/null && break
done

# Browser öffnen
am start -a android.intent.action.VIEW \
    -d "http://localhost:$FLOW_PORT" 2>/dev/null || true

command -v termux-toast &>/dev/null && \
    termux-toast -s "tachyflow läuft — im Browser Start drücken"

# Vordergrund halten bis Ctrl+C
trap "kill $FLOW_PID 2>/dev/null" EXIT INT TERM
wait $FLOW_PID
