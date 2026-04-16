"""
GeoCOM Verbindung für tachylog.

Auf Android/Termux wird Bluetooth über eine TCP-Bridge angesprochen:
  1. App "BT/TCP Bridge" verbindet sich mit der Totalstation (Bluetooth SPP)
  2. App öffnet TCP-Server auf localhost:4444
  3. tachylog verbindet sich via TCP: --port tcp://localhost:4444

Auf Linux/Desktop (mit rfcomm) kann auch direkt seriell verbunden werden:
  tachylog collect --port /dev/rfcomm0

Port-Format:
  tcp://localhost:4444   → TCP (Android + BT/TCP Bridge App)
  tcp://192.168.1.5:4444 → TCP über Netzwerk
  /dev/rfcomm0           → Seriell (Linux mit rfcomm)
  COM3                   → Seriell (Windows)
"""

import socket
import serial
import logging
from dataclasses import dataclass, field
from typing import Optional

from .geocom_constants import RC, RPC, TMC_MODE, build_request, parse_response

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Verbindungskonfiguration für die Totalstation."""
    port: str = "tcp://localhost:4444"  # TCP-Bridge (Standard für Android)
    baudrate: int = 9600                # Nur relevant für serielle Verbindung
    timeout: float = 5.0               # Timeout in Sekunden
    measure_wait: float = 0.8          # Wartezeit nach TMC_DO_MEASURE
    reflectorless: bool = True         # True = reflektorlos (ohne Prisma)
    reconnect_delay: float = 3.0       # Wartezeit vor Reconnect-Versuch


class TotalstationConnection:
    """
    Verbindung zur Leica Totalstation über GeoCOM-Protokoll.

    Unterstützt TCP (für Android/BT-Bridge) und seriell (Linux/Windows).

    Verwendung:
        config = ConnectionConfig(port="tcp://localhost:4444")
        with TotalstationConnection(config) as conn:
            result = conn.send("COM_GET_SW_VERSION")
    """

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self._socket: Optional[socket.socket] = None
        self._serial: Optional[serial.Serial] = None
        self._use_tcp = config.port.startswith("tcp://")

    # ── TCP ──────────────────────────────────────────────────────────────

    def _tcp_host_port(self):
        """Parst 'tcp://host:port' → (host, port)."""
        addr = self.config.port[len("tcp://"):]
        host, port = addr.rsplit(":", 1)
        return host, int(port)

    def _tcp_connect(self) -> bool:
        host, port = self._tcp_host_port()
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.config.timeout)
            s.connect((host, port))
            self._socket = s
            logger.info(f"TCP verbunden mit {host}:{port}")
            return True
        except OSError as e:
            logger.error(f"TCP Verbindungsfehler: {e}")
            return False

    def _tcp_send(self, data: bytes) -> str:
        """Sendet Bytes, liest bis Newline, gibt String zurück."""
        self._socket.sendall(data)
        raw = b""
        while not raw.endswith(b"\n"):
            chunk = self._socket.recv(256)
            if not chunk:
                break
            raw += chunk
        return raw.decode("ascii", errors="replace")

    # ── Seriell ──────────────────────────────────────────────────────────

    def _serial_connect(self) -> bool:
        try:
            self._serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.config.timeout,
            )
            logger.info(f"Seriell verbunden mit {self.config.port}")
            return True
        except serial.SerialException as e:
            logger.error(f"Serieller Verbindungsfehler: {e}")
            return False

    def _serial_send(self, data: bytes) -> str:
        self._serial.reset_input_buffer()
        self._serial.write(data)
        return self._serial.readline().decode("ascii", errors="replace")

    # ── Öffentliche API ───────────────────────────────────────────────────

    def connect(self) -> bool:
        """Verbindung aufbauen. True wenn erfolgreich."""
        if self._use_tcp:
            return self._tcp_connect()
        return self._serial_connect()

    def disconnect(self):
        """Verbindung trennen."""
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None
        logger.info("Verbindung getrennt")

    def is_connected(self) -> bool:
        if self._use_tcp:
            return self._socket is not None
        return self._serial is not None and self._serial.is_open

    def send_command(self, rpc: int, *params) -> dict:
        """
        Sendet einen GeoCOM-Befehl und gibt die geparste Antwort zurück.

        Rückgabe: {"rc": 0, "values": [...], "raw": "..."}
                  {"rc": -1, "error": "...", "values": [], "raw": ""}
        """
        if not self.is_connected():
            return {"rc": -1, "error": "Nicht verbunden", "values": [], "raw": ""}

        request = build_request(rpc, *params)
        logger.debug(f"→ {request.strip()}")

        try:
            data = request.encode("ascii")
            if self._use_tcp:
                raw = self._tcp_send(data)
            else:
                raw = self._serial_send(data)

            logger.debug(f"← {raw.strip()}")
            return parse_response(raw)

        except (serial.SerialException, OSError) as e:
            logger.error(f"Kommunikationsfehler: {e}")
            self.disconnect()
            return {"rc": -1, "error": str(e), "values": [], "raw": ""}

    def ping(self) -> bool:
        """Testet ob die Totalstation antwortet."""
        result = self.send_command(RPC.COM_GET_SW_VERSION)
        return RC.is_ok(result.get("rc", -1))

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
