"""
Verbindungskonfiguration für tachylog.

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

from dataclasses import dataclass


@dataclass
class ConnectionConfig:
    """Verbindungskonfiguration für die Totalstation."""
    port: str = "tcp://localhost:4444"  # TCP-Bridge (Standard für Android)
    baudrate: int = 115200              # Nur relevant für serielle Verbindung
    timeout: float = 5.0               # Timeout in Sekunden
    reconnect_delay: float = 3.0       # Wartezeit vor Reconnect-Versuch
