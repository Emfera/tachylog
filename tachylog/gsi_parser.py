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
  11  → PID / Punktnummer

  Mit Maske 1 (TS07 Standard, Koordinaten):
  21  → Easting  (E / Rechtswert) in mm → /1000 = Meter
  22  → Northing (N / Hochwert)   in mm → /1000 = Meter
  31  → Height   (H / Höhe)       in mm → /1000 = Meter

  Alternative Indizes (andere Masken):
  81  → Easting  (E / Rechtswert) in mm → /1000 = Meter
  82  → Northing (N / Hochwert)   in mm → /1000 = Meter
  83  → Height   (H / Höhe)       in mm → /1000 = Meter

Beispiele vom TS07 (GSI16, Maske 1):
  Als direkte GSI-Zeile:
    *110007+0000000000LE01019 21.032+0000000011112846 22.032+0000000007350902 31.06+0000000000054191

  Als GeoCOM-Response:
    %R1P,0,0:0,*110002+0000000000FP0001 810006+0000000001986199 820006+0000000007347358 830006+0000000000012034
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class GSIMeasurement:
    """Eine geparste GSI-Messung vom TS07."""
    pid: str      # Punktnummer / PID
    e: float      # Easting  (Rechtswert) in Meter
    n: float      # Northing (Hochwert)   in Meter
    h: float      # Height   (Höhe)       in Meter
    raw: str      # Rohstring für Debugging


def _parse_gsi_words(payload: str) -> dict:
    """
    Parst GSI-Wörter aus einem Payload-String.

    Wörter sind durch Leerzeichen getrennt.
    Jedes Wort: Prefix (Ziffern + Info) + Vorzeichen + Wert.
    Index = erste 2 Ziffern des Prefix.

    Gibt {index: wert_string} zurück.
    """
    words = {}
    # * am Anfang entfernen (GSI-Zeilenstarter)
    payload = payload.lstrip('*').strip()

    for token in payload.split():
        if not token:
            continue
        # Vorzeichen finden (+ oder - nach dem Prefix)
        pm = token.find('+')
        if pm == -1:
            pm = token.find('-', 1)  # ab Position 1, um führendes - zu überspringen
        if pm <= 0:
            continue

        prefix = token[:pm]
        value  = token[pm:]

        # Erste 2 Ziffern des Prefix = Index
        digits = re.match(r'(\d+)', prefix)
        if not digits:
            continue
        index = int(digits.group(1)[:2])
        words[index] = value

    return words


def _gsi_to_float(value: str) -> Optional[float]:
    """
    Konvertiert einen GSI-Wert zu float in Meter.

    GSI speichert Koordinaten mit implizit 3 Nachkommastellen (mm).
    Beispiele:
      '+0000000001986199' → 1986.199 m  (GSI16)
      '+00123456'         →  123.456 m  (GSI8)
      '-00001234'         →   -1.234 m
    """
    try:
        sign = -1 if value.startswith('-') else 1
        raw = value.lstrip('+-').lstrip('0') or '0'
        return sign * int(raw) / 1000.0
    except (ValueError, TypeError):
        return None


def _gsi_to_pid(value: str) -> Optional[str]:
    """
    Extrahiert PID aus einem GSI-Wort-11-Wert.
    Entfernt Vorzeichen und führende Nullen.

    Beispiele:
      '+0000000000FP0001'  → 'FP0001'
      '+0000000000LE01'    → 'LE01'
      '+00000FP00010001'   → 'FP00010001'
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
        # GeoCOM-Response: RC prüfen
        rc_match = re.search(r'%R1P,\d+,\d+:(\d+)', response)
        if rc_match:
            rc = int(rc_match.group(1))
            if rc not in (0, 1283, 1284, 1285, 1288, 1289):
                return None

        # Payload nach RC extrahieren
        payload_match = re.search(r'%R1P,\d+,\d+:\d+,(.*)', response)
        if not payload_match:
            return None
        return payload_match.group(1).strip()

    elif response.startswith('*') or (response and response[0].isdigit()):
        # Direkte GSI-Zeile
        return response

    return None


def parse_gsi_response(response: str) -> Optional[GSIMeasurement]:
    """
    Parst eine GSI-Response (GeoCOM oder direkt).

    Gibt GSIMeasurement zurück oder None wenn kein gültiger Datensatz.
    """
    if not response:
        return None

    payload = _extract_gsi_payload(response)
    if not payload:
        return None

    words = _parse_gsi_words(payload)

    # PID (Word 11)
    pid_raw = words.get(11)
    if pid_raw is None:
        return None
    pid = _gsi_to_pid(pid_raw)
    if not pid:
        return None

    # Koordinaten: Maske 1 = 21/22/31, andere Masken = 81/82/83
    # Probiere beide Varianten, Maske 1 hat Vorrang
    e_raw = words.get(21) or words.get(81)
    n_raw = words.get(22) or words.get(82)
    h_raw = words.get(31) or words.get(83)

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
    Gleiche Messung = gleicher PID + gleiche Koordinaten.
    """
    return f"{m.pid}:{m.e:.3f}:{m.n:.3f}:{m.h:.3f}"
