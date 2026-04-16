"""
PID-Parser für surveypipe.

PID-Format: CCSSSSNNNN (10 Zeichen)
  CC   = Code (2 Stellen)  — verweist auf Code-Tabelle
  SSSS = SE-ID (4 Stellen) — Survey Element ID (welches Feature)
  NNNN = Sequenz (4 Stellen) — Reihenfolge der Punkte innerhalb des Features

Beispiele:
  FP00010001 → Code=FP, SE-ID=0001, Seq=0001 → 1. Punkt von Feature 0001 (Fundpunkt)
  WA00020003 → Code=WA, SE-ID=0002, Seq=0003 → 3. Punkt von Feature 0002 (Wand-Linie)
  PF00010001 → Code=PF, SE-ID=0001, Seq=0001 → Pfostenloch 0001

Codes < 2 Zeichen oder > 10 Zeichen gesamt sind ungültig.
"""

import re
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────
# Datenklassen
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class ParsedPID:
    """Eine geparste Punkt-ID."""
    raw: str       # Original-PID, z.B. "FP00010001"
    code: str      # 2-stelliger Code, z.B. "FP"
    se_id: int     # Survey Element ID (0-9999), z.B. 1
    seq: int       # Sequenz (1-9999), z.B. 1

    @property
    def feature_key(self) -> tuple[str, int]:
        """Eindeutiger Schlüssel für ein Feature: (code, se_id)."""
        return (self.code, self.se_id)

    def __str__(self) -> str:
        return f"{self.raw} (Code={self.code}, SE={self.se_id:04d}, Seq={self.seq:04d})"


# ─────────────────────────────────────────────
# Regex-Pattern
# ─────────────────────────────────────────────

# Exaktes Format: 2 Buchstaben/Ziffern + 4 Ziffern + 4 Ziffern = 10 Zeichen
_PID_PATTERN = re.compile(r'^([A-Z0-9]{2})(\d{4})(\d{4})$', re.IGNORECASE)


# ─────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────

def parse_pid(pid: str) -> Optional[ParsedPID]:
    """
    Parst eine PID und gibt ein ParsedPID-Objekt zurück.
    Gibt None zurück wenn die PID ungültig ist.

    Beispiel:
      parse_pid("FP00010001") → ParsedPID(raw="FP00010001", code="FP", se_id=1, seq=1)
      parse_pid("invalid")    → None
    """
    if not pid or not isinstance(pid, str):
        return None

    pid = pid.strip().upper()
    m = _PID_PATTERN.match(pid)
    if not m:
        return None

    code = m.group(1).upper()
    se_id = int(m.group(2))
    seq = int(m.group(3))

    # Sequenz muss >= 1 sein (0000 ist kein gültiger Punkt)
    if seq < 1:
        return None

    return ParsedPID(raw=pid, code=code, se_id=se_id, seq=seq)


def is_valid_pid(pid: str) -> bool:
    """Schnellprüfung ob eine PID gültig ist."""
    return parse_pid(pid) is not None


def validate_pid_sequence(pids: list[str]) -> dict:
    """
    Prüft eine Liste von PIDs auf Konsistenz.

    Gibt ein Dict zurück:
      {
        "valid": [ParsedPID, ...],
        "invalid": ["RAW_PID", ...],
        "warnings": ["Warnung 1", ...],
        "features": {("FP", 1): [ParsedPID, ...], ...}
      }
    """
    valid = []
    invalid = []
    warnings = []
    features: dict[tuple, list] = {}

    for pid_str in pids:
        parsed = parse_pid(pid_str)
        if parsed is None:
            invalid.append(pid_str)
        else:
            valid.append(parsed)
            key = parsed.feature_key
            if key not in features:
                features[key] = []
            features[key].append(parsed)

    # Sequenz-Lücken prüfen
    for key, pts in features.items():
        seqs = sorted(p.seq for p in pts)
        for i, (a, b) in enumerate(zip(seqs, seqs[1:])):
            if b - a > 1:
                warnings.append(
                    f"Feature {key[0]}{key[1]:04d}: Sequenzlücke zwischen {a:04d} und {b:04d}"
                )

    return {
        "valid": valid,
        "invalid": invalid,
        "warnings": warnings,
        "features": features,
    }


def next_pid(pid: str) -> str:
    """
    Gibt den nächsten PID in der Sequenz zurück (Sequenznummer +1).
    Beispiel: 'FP00010003' → 'FP00010004'
    """
    parsed = parse_pid(pid)
    if parsed is None:
        return pid
    next_seq = parsed.seq + 1
    if next_seq > 9999:
        next_seq = 1
    return f"{parsed.code}{parsed.se_id:04d}{next_seq:04d}"
