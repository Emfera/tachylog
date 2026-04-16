"""
tachylog — GSI-Datenlogger für Leica Flexline Totalstationen.

Empfängt Messungen in Echtzeit via Bluetooth und speichert sie
formatneutral als CSV, SQLite, GSI oder GeoJSON.
PID ist ein freier String — kein Format wird erzwungen.

Unterstützt:
- Leica Totalstationen via GSI (Bluetooth/TCP-Bridge)
- GNSS CSV-Import (Emlid Flow kompatibel)
"""

__version__ = "1.1.0"
__author__ = "Martin Fera <martin.fera@univie.ac.at>"
