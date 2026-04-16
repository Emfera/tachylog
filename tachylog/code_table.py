"""
Code-Tabelle für surveypipe.

Die Code-Tabelle definiert wie ein 2-stelliger Code interpretiert wird:
  - Welche Geometrie entsteht (Punkt, Linie, Polygon)
  - Welche Beschreibung der Code hat

Inspiration: ArchSurv4QGIS Shape-Type-Spektrum
(https://github.com/archsurv4qgis/ArchSurv4QGIS)

Die Standard-Code-Tabelle enthält typische Codes für archäologische
Feldvermessung. Du kannst sie erweitern oder mit einer eigenen JSON-Datei
überschreiben.

Geometrie-Typen:
  "point"   → Ein einzelner Punkt (PointZ). Sequenz egal.
  "line"    → Linie (LineStringZ). Punkte werden in Seq-Reihenfolge verbunden.
  "polygon" → Polygon (PolygonZ). Wie Linie, aber automatisch geschlossen.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────
# Geometrie-Typen
# ─────────────────────────────────────────────

class GeomType(str, Enum):
    POINT   = "point"
    LINE    = "line"
    POLYGON = "polygon"


# ─────────────────────────────────────────────
# Code-Definition
# ─────────────────────────────────────────────

@dataclass
class CodeDef:
    """Definition eines Survey-Codes."""
    code: str           # 2-stelliger Code (z.B. "FP")
    geom: GeomType      # Geometrie-Typ
    description: str    # Beschreibung (z.B. "Fundpunkt")
    category: str = ""  # Kategorie (z.B. "Funde", "Strukturen")

    def __post_init__(self):
        self.code = self.code.strip().upper()
        if len(self.code) != 2:
            raise ValueError(f"Code muss genau 2 Zeichen haben: '{self.code}'")
        if isinstance(self.geom, str):
            self.geom = GeomType(self.geom)


# ─────────────────────────────────────────────
# Standard-Code-Tabelle (Archäologie)
# Erweiterter Katalog basierend auf ArchSurv4QGIS
# ─────────────────────────────────────────────

DEFAULT_CODES: list[dict] = [
    # ── Einzelpunkte ──────────────────────────────────────
    {"code": "HP", "geom": "point",   "description": "Höhenpunkt",             "category": "Höhen"},
    {"code": "FP", "geom": "point",   "description": "Fundpunkt",              "category": "Funde"},
    {"code": "PR", "geom": "point",   "description": "Probe",                  "category": "Proben"},
    {"code": "PP", "geom": "point",   "description": "Passpunkt / Referenzpunkt","category": "Geodäsie"},
    {"code": "SP", "geom": "point",   "description": "Standpunkt (Instrument)","category": "Geodäsie"},
    {"code": "KP", "geom": "point",   "description": "Kontrollpunkt",          "category": "Geodäsie"},
    {"code": "PZ", "geom": "point",   "description": "Pfostenzentrum",         "category": "Strukturen"},
    {"code": "GS", "geom": "point",   "description": "Grabungsstelle",         "category": "Strukturen"},

    # ── Linien ────────────────────────────────────────────
    {"code": "WA", "geom": "line",    "description": "Wand / Mauer",           "category": "Strukturen"},
    {"code": "GR", "geom": "line",    "description": "Graben",                 "category": "Strukturen"},
    {"code": "BR", "geom": "line",    "description": "Bruchkante / Abbruch",   "category": "Strukturen"},
    {"code": "SC", "geom": "line",    "description": "Schnittgrenze",          "category": "Grabung"},
    {"code": "PF", "geom": "line",    "description": "Profilführung",          "category": "Grabung"},
    {"code": "HK", "geom": "line",    "description": "Höhenkurve",             "category": "Höhen"},
    {"code": "ST", "geom": "line",    "description": "Straße / Weg",           "category": "Strukturen"},
    {"code": "ZA", "geom": "line",    "description": "Zaun / Grenze",          "category": "Strukturen"},

    # ── Polygone ──────────────────────────────────────────
    {"code": "BF", "geom": "polygon", "description": "Befund",                 "category": "Befunde"},
    {"code": "GH", "geom": "polygon", "description": "Gebäude / Haus",         "category": "Strukturen"},
    {"code": "RA", "geom": "polygon", "description": "Raum",                   "category": "Strukturen"},
    {"code": "GF", "geom": "polygon", "description": "Grabungsfeld / Schnitt", "category": "Grabung"},
    {"code": "PL", "geom": "polygon", "description": "Planum",                 "category": "Grabung"},
    {"code": "GE", "geom": "polygon", "description": "Gesamtgrabungsfläche",   "category": "Grabung"},
    {"code": "PO", "geom": "polygon", "description": "Pfostenloch",            "category": "Befunde"},
    {"code": "GU", "geom": "polygon", "description": "Grube",                  "category": "Befunde"},
    {"code": "HE", "geom": "polygon", "description": "Herd",                   "category": "Befunde"},
    {"code": "SK", "geom": "polygon", "description": "Skelett / Bestattung",   "category": "Bestattungen"},
]


# ─────────────────────────────────────────────
# Code-Tabelle
# ─────────────────────────────────────────────

class CodeTable:
    """
    Verwaltet die Code-Tabelle.

    Verwendung:
        ct = CodeTable()                          # Standard-Codes
        ct = CodeTable.from_json("codes.json")   # Eigene Codes
        ct.get("FP")                              # → CodeDef(...)
        ct.geom_type("FP")                        # → GeomType.POINT
    """

    def __init__(self, codes: Optional[list[CodeDef]] = None):
        self._codes: dict[str, CodeDef] = {}
        if codes:
            for c in codes:
                self._codes[c.code] = c
        else:
            # Standard-Codes laden
            for d in DEFAULT_CODES:
                c = CodeDef(**d)
                self._codes[c.code] = c

    @classmethod
    def from_json(cls, path: str | Path) -> "CodeTable":
        """Lädt eine Code-Tabelle aus einer JSON-Datei."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        codes = [CodeDef(**d) for d in data]
        return cls(codes)

    def to_json(self, path: str | Path):
        """Speichert die Code-Tabelle als JSON-Datei."""
        data = [
            {"code": c.code, "geom": c.geom.value,
             "description": c.description, "category": c.category}
            for c in self._codes.values()
        ]
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get(self, code: str) -> Optional[CodeDef]:
        """Gibt die Code-Definition zurück, oder None wenn unbekannt."""
        return self._codes.get(code.upper())

    def geom_type(self, code: str) -> Optional[GeomType]:
        """Gibt den Geometrie-Typ für einen Code zurück."""
        c = self.get(code)
        return c.geom if c else None

    def is_known(self, code: str) -> bool:
        """True wenn der Code bekannt ist."""
        return code.upper() in self._codes

    def all_codes(self) -> list[CodeDef]:
        """Gibt alle Code-Definitionen zurück, sortiert nach Code."""
        return sorted(self._codes.values(), key=lambda c: c.code)

    def add(self, code_def: CodeDef):
        """Fügt einen Code hinzu oder überschreibt einen bestehenden."""
        self._codes[code_def.code] = code_def

    def __len__(self) -> int:
        return len(self._codes)

    def __repr__(self) -> str:
        return f"CodeTable({len(self)} Codes)"


# Fertige Standard-Instanz (direkt importierbar)
CODE_TABLE = CodeTable()
