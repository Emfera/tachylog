"""
GSI-Parser für tachylog.

Unterstützt GSI8 und GSI16, sowohl als GeoCOM-Response (%R1P,...)
als auch als direkte GSI-Zeile (*110002+...).

GSI-Wort-Format:
  GSI8:  IIIUU+VVVVVVVV        (8-stelliger Wert)
  GSI16: IIIIUU+VVVVVVVVVVVVVVVV  (16-stelliger Wert)

  III/IIII = Word-Index (erste 2 Ziffern sind der eigentliche Index)
  UU       = Einheit/Format-Info
  +/-      = Vorzeichen
  V...     = Wert (führende Nullen, letzte 3 Stellen = mm)

Relevante Word-Indizes (erste 2 Ziffern):
  11  → PID / Punktnummer (opaker String, wird unverändert übernommen)

  Koordinaten (bevorzugt — Maske 2):
  81  → Easting  (E / Rechtswert) in mm → /Divisor = Meter
  82  → Northing (N / Hochwert)   in mm → /Divisor = Meter
  83  → Height   (H / Höhe)       in mm → /Divisor = Meter

  Koordinaten (Fallback — Maske 1, falls 81/82/83 fehlen):
  21  → Easting  (je nach Maskenkonfiguration)
  22  → Northing
  31  → Height

Beispiele vom TS07 (GSI16, Maske 2):
  Als direkte GSI-Zeile:
    *110007+0000000000OT00010001 810006+0000000011112846 820006+0000000007350902 830006+0000000000054191

  Als GeoCOM-Response:
    %R1P,0,0:0,*110002+0000000000FP0001 810006+0000000001986199 820006+0000000007347358 830006+0000000000012034
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class GSIMeasurement:
    """Eine geparste GSI-Messung vom TS07."""
    pid: str      # Punktnummer / PID (opaker String, unverändert vom Instrument)
    e: float      # Easting  (Rechtswert) in Meter
    n: float      # Northing (Hochwert)   in Meter
    h: float      # Height   (Höhe)       in Meter
    raw: str      # Rohstring für Debugging und GSI-Archivierung


# GSI Unit-Code → Divisor (Wert / Divisor = Meter)
_GSI_UNIT_DIVISOR = {
    0:  1.0,
    1:  10.0,
    2:  100.0,
    3:  1000.0,     # mm (GSI8 Standard)
    4:  10000.0,
    5:  100000.0,
    6:  10000.0,    # 0.1mm (GSI16 Koordinaten, Unit 06)
    7:  100000.0,
    8:  100000.0,
}


def _parse_gsi_words(payload: str) -> dict:
    """
    Parst GSI-Wörter aus einem Payload-String.
    Gibt {index: (unit_code, wert_string)} zurück.
    """
    words = {}
    payload = payload.lstrip('*').strip()

    for token in payload.split():
        if not token:
            continue
        pm = token.find('+')
        if pm == -1:
            pm = token.find('-', 1)
        if pm <= 0:
            continue

        prefix = token[:pm]
        value  = token[pm:]

        digits = re.match(r'(\d+)', prefix)
        if not digits:
            continue
        index = int(digits.group(1)[:2])

        unit_match = re.search(r'\.(\d{1,2})$', prefix)
        unit = int(unit_match.group(1)) if unit_match else 3

        words[index] = (unit, value)

    return words


def _gsi_to_float(entry) -> Optional[float]:
    """Konvertiert einen GSI-Wert zu float in Meter."""
    try:
        if isinstance(entry, tuple):
            unit, value = entry
        else:
            unit, value = 3, entry
        divisor = _GSI_UNIT_DIVISOR.get(unit, 1000.0)
        sign = -1 if value.startswith('-') else 1
        raw = value.lstrip('+-').lstrip('0') or '0'
        return sign * int(raw) / divisor
    except (ValueError, TypeError):
        return None


def _gsi_to_pid(value: str) -> Optional[str]:
    """
    Extrahiert PID aus einem GSI-Wort-11-Wert.

    Entfernt Vorzeichen und führende Nullen.
    PID ist ein opaker String — kein Format wird erzwungen.

    Beispiele:
      '+0000000000OT00010001'  → 'OT00010001'
      '+0000000000FP0001'      → 'FP0001'
      '+0000000000LE01'        → 'LE01'
    """
    raw = value.lstrip('+-').lstrip('0')
    return raw if raw else None


def _extract_gsi_payload(response: str) -> Optional[str]:
    """
    Extrahiert den GSI-Payload aus verschiedenen Response-Formaten.

    Unterstützt:
    1. GeoCOM-Response: %R1P,0,0:0,*110002+...
    2. Direkte GSI-Zeile: *110002+...
    3. GeoCOM ohne *: %R1P,0,0:0,110002+...
    """
    response = response.strip()

    if '%R1P' in response:
        rc_match = re.search(r'%R1P,\d+,\d+:(\d+)', response)
        if rc_match:
            rc = int(rc_match.group(1))
            if rc not in (0, 1283, 1284, 1285, 1288, 1289):
                return None

        payload_match = re.search(r'%R1P,\d+,\d+:\d+,(.*)', response)
        if not payload_match:
            return None
        return payload_match.group(1).strip()

    elif response.startswith('*') or (response and response[0].isdigit()):
        return response

    return None


def parse_gsi_response(response: str) -> Optional[GSIMeasurement]:
    """
    Parst eine GSI-Response (GeoCOM oder direkt).

    Gibt GSIMeasurement zurück oder None wenn kein gültiger Datensatz.
    Die PID wird unverändert übernommen — kein Format wird erzwungen.
    """
    if not response:
        return None

    payload = _extract_gsi_payload(response)
    if not payload:
        return None

    words = _parse_gsi_words(payload)

    # PID (Word 11) — opaker String
    pid_raw = words.get(11)
    if pid_raw is None:
        return None
    pid = _gsi_to_pid(pid_raw[1])  # pid_raw = (unit, value)
    if not pid:
        return None

    # Koordinaten: bevorzugt 81/82/83 (Maske 2), Fallback 21/22/31 (Maske 1)
    e_raw = words.get(81) or words.get(21)
    n_raw = words.get(82) or words.get(22)
    h_raw = words.get(83) or words.get(31)

    if None in (e_raw, n_raw, h_raw):
        return None

    e = _gsi_to_float(e_raw)
    n = _gsi_to_float(n_raw)
    h = _gsi_to_float(h_raw)

    if None in (e, n, h):
        return None

    return GSIMeasurement(pid=pid, e=e, n=n, h=h, raw=response.strip())


def measurement_key(m: GSIMeasurement) -> str:
    """
    Eindeutiger Schlüssel für Duplikat-Erkennung.

    Gleiche Messung = gleiche PID + gleiche Koordinaten (mm-Genauigkeit).
    Verhindert wiederholtes Speichern der letzten Messung beim Polling.
    """
    return f"{m.pid}:{m.e:.3f}:{m.n:.3f}:{m.h:.3f}"
