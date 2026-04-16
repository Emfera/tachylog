"""
tachylog — GSI Collector

Architektur (aktives Polling):
  1. tachylog sendet %R1Q,2115: an die Totalstation (GeoCOM Request)
  2. TS07 antwortet mit letztem Messsatz im GSI-Format
  3. tachylog liest alle verfügbaren Bytes
  4. GSI-Zeilen werden geparst und in alle aktiven Ausgaben geschrieben
  5. Duplikat-Schutz: nur neue Messungen werden gespeichert
  6. Optional: PID-Validierung gegen Schema (nur Warnungen, kein Abbruch)

Das Instrument behält die volle Kontrolle:
  - PID wird am TS07 eingegeben (freies Format)
  - Messung wird am TS07 ausgelöst
  - tachylog pollt und speichert automatisch

Verbindung über TCP-Bridge (Android):
  BT/TCP Bridge App: Bluetooth SPP → TCP localhost:4444
  tachylog: --port tcp://localhost:4444
"""

import socket
import time
import logging
from dataclasses import dataclass
from typing import Optional

from .connection import ConnectionConfig
from .gsi_parser import parse_gsi_response, measurement_key
from .output import OutputManager
from .schema_validator import SchemaDef

logger = logging.getLogger(__name__)

# GeoCOM Request: letzten Messsatz als GSI abrufen
GEOCOM_GET_LAST_GSI = b"%R1Q,2115:\r\n"


@dataclass
class CollectorConfig:
    """Konfiguration für den Collector."""
    poll_interval: float = 0.2
    read_timeout: float = 1.0
    reconnect_delay: float = 3.0


def _tcp_host_port(port_str: str):
    addr = port_str[len("tcp://"):]
    host, port = addr.rsplit(":", 1)
    return host, int(port)


def _connect_tcp(host: str, port: int, timeout: float = 5.0) -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, port))
    return s


def _read_available(sock: socket.socket, read_timeout: float) -> str:
    sock.settimeout(read_timeout)
    data = b""
    try:
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError("Verbindung getrennt")
            data += chunk
            sock.settimeout(0.1)
    except socket.timeout:
        pass
    return data.decode("ascii", errors="replace")


def _extract_lines(text: str) -> list:
    lines = []
    for line in text.replace("\r", "\n").split("\n"):
        line = line.strip()
        if line:
            lines.append(line)
    return lines


def run_collector(
    conn_config: ConnectionConfig,
    db_path: Optional[str] = None,
    poll_interval: float = 0.2,
    csv_path: Optional[str] = None,
    gsi_path: Optional[str] = None,
    geojson_path: Optional[str] = None,
    schema: Optional[SchemaDef] = None,
):
    """
    Startet den Polling-Collector.

    Schreibt Messungen in alle aktiven Ausgabeformate.
    Prüft PIDs optional gegen ein Schema (nur Warnungen).
    Läuft bis Ctrl+C.
    """
    if not any([db_path, csv_path, gsi_path, geojson_path]):
        raise ValueError(
            "Mindestens ein Ausgabeformat muss angegeben werden "
            "(--db, --csv, --gsi oder --geojson)"
        )

    if schema is None:
        schema = SchemaDef.free()

    use_tcp = conn_config.port.startswith("tcp://")
    if not use_tcp:
        raise NotImplementedError(
            "Nur TCP unterstützt — bitte BT/TCP Bridge App verwenden"
        )

    host, port = _tcp_host_port(conn_config.port)

    output = OutputManager(
        db=db_path,
        csv_path=csv_path,
        gsi_path=gsi_path,
        geojson_path=geojson_path,
    )
    output.open()

    print(f"\n  tachylog — GSI Collector")
    print(f"  Port:  {conn_config.port}")
    if schema.is_active():
        print(f"  Schema: {schema.summary()}")
    for line in output.active_outputs():
        print(f"  {line}")
    print(f"\n  Bedienung: Alles am Instrument (TS07)")
    print(f"  PID eingeben + Messung auslösen → tachylog speichert automatisch")
    print(f"  Beenden: Ctrl+C\n")

    last_key = None
    errors = 0

    def connect_loop() -> socket.socket:
        while True:
            print(f"  Verbinde mit {conn_config.port}...", end="", flush=True)
            try:
                s = _connect_tcp(host, port, timeout=5.0)
                print(" ✓")
                return s
            except OSError as e:
                print(f" ✗  ({e})")
                print(f"  Retry in {conn_config.reconnect_delay}s...")
                time.sleep(conn_config.reconnect_delay)

    sock = connect_loop()
    print("  Warte auf Messungen...\n")

    try:
        while True:
            # GeoCOM Request senden
            try:
                sock.settimeout(5.0)
                sock.sendall(GEOCOM_GET_LAST_GSI)
            except OSError as e:
                errors += 1
                logger.warning(f"Sendefehler ({errors}x): {e} — reconnecte...")
                try:
                    sock.close()
                except OSError:
                    pass
                time.sleep(conn_config.reconnect_delay)
                sock = connect_loop()
                print("  Warte auf Messungen...\n")
                continue

            # Antwort lesen
            try:
                raw = _read_available(sock, read_timeout=1.0)
            except ConnectionError as e:
                errors += 1
                logger.warning(f"Lesefehler ({errors}x): {e} — reconnecte...")
                try:
                    sock.close()
                except OSError:
                    pass
                time.sleep(conn_config.reconnect_delay)
                sock = connect_loop()
                print("  Warte auf Messungen...\n")
                continue

            errors = 0

            if raw:
                logger.debug(f"← {repr(raw)}")

            for line in _extract_lines(raw):
                measurement = parse_gsi_response(line)
                if measurement is None:
                    continue

                key = measurement_key(measurement)
                if key == last_key:
                    continue

                last_key = key

                # Schema-Validierung (nur Warnungen, kein Abbruch)
                if schema.is_active():
                    warnings = schema.validate(measurement.pid)
                    for w in warnings:
                        print(f"  [WARN] {w}")

                output.write(measurement)

                print(f"  [{output.count:4d}] {measurement.pid:<12}"
                      f"  E={measurement.e:12.3f}"
                      f"  N={measurement.n:12.3f}"
                      f"  H={measurement.h:8.3f}")

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print(f"\n\n  Beendet. {output.count} Punkte gespeichert.")
        for line in output.active_outputs():
            print(f"  {line}")
        if db_path and output.count > 0:
            print(f"\n  Nächster Schritt: Export oder Weiterverarbeitung\n")
    finally:
        output.close()
        try:
            sock.close()
        except OSError:
            pass
