"""
tachylog — Schema-Validator

Optionale, nicht-blockierende Gültigkeitsprüfung von PIDs gegen ein
Downstream-Tool-Schema (z. B. Gladiator_2, AS4QGIS).

Warnungen werden ausgegeben, Messungen NIEMALS verworfen.

Verwendung:
    schema = SchemaDef.load("schemas/gladiator2.json")
    warnings = schema.validate("OT00010001")

    schema = SchemaDef.free()   # Kein Schema — keine Prüfung
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CodeDef:
    """Definition eines Codes im Schema."""
    code: str
    geometry: str   # "point" | "line" | "polygon"
    label: str


@dataclass
class SchemaDef:
    """
    Geladenes Schema für ein Downstream-Tool.

    Attribute:
        name         — Name des Tools (z. B. "Gladiator_2")
        pid_length   — Erwartete PID-Länge (None = keine Prüfung)
        pid_pattern  — Kompilierter Regex für PID-Format (None = keine Prüfung)
        known_codes  — Menge bekannter 2-Buchstaben-Codes (leer = keine Prüfung)
        code_geometry — Mapping code → Geometrietyp
        codes        — Vollständige Code-Definitionen
    """
    name: str
    pid_length: Optional[int]
    pid_pattern: Optional[re.Pattern]
    known_codes: set
    code_geometry: dict
    codes: list = field(default_factory=list)

    # ── Laden ──────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path) -> "SchemaDef":
        """Lädt ein Schema aus einer JSON-Datei."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        codes_raw = data.get("codes", [])
        codes = [CodeDef(
            code=c["code"].upper(),
            geometry=c.get("geometry", "point"),
            label=c.get("label", ""),
        ) for c in codes_raw]

        pid_fmt = data.get("pid_format")
        pid_len = data.get("pid_length")

        return cls(
            name=data.get("name", "unnamed"),
            pid_length=pid_len if isinstance(pid_len, int) else None,
            pid_pattern=_compile_pattern(pid_fmt) if pid_fmt else None,
            known_codes={c.code for c in codes},
            code_geometry={c.code: c.geometry for c in codes},
            codes=codes,
        )

    @classmethod
    def free(cls) -> "SchemaDef":
        """Kein Schema — keine Prüfung. Default wenn kein --schema angegeben."""
        return cls(
            name="free",
            pid_length=None,
            pid_pattern=None,
            known_codes=set(),
            code_geometry={},
            codes=[],
        )

    # ── Validierung ────────────────────────────────────────────────────────

    def validate(self, pid: str) -> list[str]:
        """
        Prüft eine PID gegen das Schema.

        Gibt eine Liste von Warnungs-Strings zurück.
        Leere Liste = keine Auffälligkeiten.
        """
        if self.name == "free":
            return []

        warnings = []

        # Längenprüfung
        if self.pid_length is not None and len(pid) != self.pid_length:
            warnings.append(
                f"PID '{pid}' hat {len(pid)} statt {self.pid_length} Zeichen"
            )

        # Format-Regex
        if self.pid_pattern is not None and not self.pid_pattern.match(pid):
            warnings.append(
                f"PID '{pid}' entspricht nicht dem Format ({self.name})"
            )

        # Code-Prüfung (erste 2 Zeichen)
        if self.known_codes and len(pid) >= 2:
            code = pid[:2].upper()
            if code not in self.known_codes:
                warnings.append(
                    f"Code '{code}' nicht in Schema '{self.name}'"
                )

        return warnings

    def geometry_for(self, pid: str) -> Optional[str]:
        """
        Gibt den Geometrietyp für einen PID zurück.
        None wenn Code unbekannt oder kein Schema geladen.
        """
        if len(pid) < 2:
            return None
        return self.code_geometry.get(pid[:2].upper())

    # ── Info ───────────────────────────────────────────────────────────────

    def is_active(self) -> bool:
        """True wenn ein echtes Schema geladen ist (nicht 'free')."""
        return self.name != "free"

    def summary(self) -> str:
        if not self.is_active():
            return "Kein Schema (freies PID-Format)"
        return (
            f"Schema: {self.name} | "
            f"PID-Länge: {self.pid_length or 'beliebig'} | "
            f"{len(self.known_codes)} Codes"
        )

    def __repr__(self) -> str:
        return f"SchemaDef(name={self.name!r}, codes={len(self.known_codes)})"


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _compile_pattern(fmt: str) -> re.Pattern:
    """
    Konvertiert ein PID-Format-Template in einen Regex.

    Format-Zeichen:
        C → [A-Z]    (Buchstabe, für Code-Stellen)
        S → \\d      (Ziffer, für SE-ID)
        N → \\d      (Ziffer, für Sequenz)
        X → \\d      (Ziffer, für Feature-Nummer, AS4QGIS)
        Y → [A-Z]   (Buchstabe, für Container, AS4QGIS)
        Z → \\d      (Ziffer, für Shape-Type, AS4QGIS)
        Andere Zeichen werden literal übernommen.
    """
    mapping = {
        "C": "[A-Z]",
        "S": r"\d",
        "N": r"\d",
        "X": r"\d",
        "Y": "[A-Z]",
        "Z": r"\d",
    }
    pattern = "".join(mapping.get(c, re.escape(c)) for c in fmt)
    return re.compile(f"^{pattern}$", re.IGNORECASE)
