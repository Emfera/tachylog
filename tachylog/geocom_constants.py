"""
GeoCOM Protokoll-Konstanten für Leica Totalstationen.
Basiert auf: Leica GeoCOM Reference Manual + tachyconnect (LfA Sachsen)
https://github.com/Landesamt-fuer-Archaeologie-Sachsen/tachyconnect

GeoCOM-Protokoll Grundformat:
  Request:  %R1Q,<RPC>:<param1>,<param2>,...
  Response: %R1P,0,<trans>:<rc>,<val1>,<val2>,...

  RPC = Remote Procedure Code (Befehlsnummer)
  rc  = Return Code (0 = OK)
"""

# ─────────────────────────────────────────────
# Return Codes (rc)
# ─────────────────────────────────────────────
class RC:
    """GeoCOM Return Codes. rc=0 bedeutet immer Erfolg."""

    OK                  = 0      # Kein Fehler
    UNDEFINED           = 1      # Unbekannter Fehler
    IVPARAM             = 2      # Ungültiger Parameter
    IVRESULT            = 3      # Ungültiges Ergebnis (Messung nicht verfügbar)
    FATAL               = 4      # Fataler Fehler
    NOT_IMPL            = 5      # Nicht implementiert
    TIME_OUT            = 6      # Timeout
    SET_INCOMPL         = 7      # Einstellung unvollständig
    ABORT               = 8      # Abgebrochen
    NOMEMORY            = 9      # Kein Speicher
    NOTINIT             = 10     # Nicht initialisiert
    SHUT_DOWN           = 12     # System fährt herunter
    SYSBUSY             = 16     # System beschäftigt
    HWFAILURE           = 17     # Hardware-Fehler
    ABORT_APPL          = 18     # Anwendung abgebrochen
    LOW_POWER           = 32     # Niedriger Akkustand
    IVVERSION           = 33     # Falsche Version
    BATT_EMPTY          = 36     # Akku leer
    NO_EVENT            = 44     # Kein Ereignis vorhanden
    OUT_OF_TEMP         = 51     # Außerhalb Temperaturbereich
    INST_MOVING         = 52     # Instrument bewegt sich
    NO_LLI_ANSWER       = 56     # GeoCOM nicht verfügbar (Instrument zu alt)

    # TMC (Tachymeter Measurement and Calculation) spezifisch
    TMC_NO_FULL_CORR    = 1283   # Nicht alle Korrekturen aktiv (Warnung, kein Fehler)
    TMC_ACCURACY_GUARANTEE = 1288  # Genauigkeit nicht garantiert (häufig bei erster Messung)
    TMC_ANGLE_OK        = 1285   # Winkel OK, Distanz fehlt
    TMC_ANGLE_NOT_FULL_CORR = 1284  # Winkel ohne vollständige Korrektur
    TMC_DIST_PPM        = 1289   # Distanz mit PPM-Korrektur
    TMC_DIST_ERROR      = 1290   # Distanzfehler
    TMC_ANGLE_ERROR     = 1291   # Winkelfehler
    TMC_NO_DIST         = 1292   # Keine Distanz gemessen

    # Meldungen die KEIN fataler Fehler sind (Messung trotzdem verwertbar)
    WARNINGS = {TMC_NO_FULL_CORR, TMC_ACCURACY_GUARANTEE, TMC_ANGLE_OK,
                TMC_ANGLE_NOT_FULL_CORR, TMC_DIST_PPM}

    @staticmethod
    def is_ok(rc: int) -> bool:
        """True wenn rc=0 (Erfolg)."""
        return rc == RC.OK

    @staticmethod
    def is_warning(rc: int) -> bool:
        """True wenn rc ein bekannter Warning-Code ist (Messung trotzdem verwertbar)."""
        return rc in RC.WARNINGS

    @staticmethod
    def is_fatal(rc: int) -> bool:
        """True wenn rc ein echter Fehler ist (Messung nicht verwertbar)."""
        return rc != RC.OK and rc not in RC.WARNINGS

    @staticmethod
    def describe(rc: int) -> str:
        """Gibt eine lesbare Beschreibung des Return Codes zurück."""
        descriptions = {
            0:    "OK",
            1:    "Unbekannter Fehler",
            2:    "Ungültiger Parameter",
            3:    "Kein Ergebnis verfügbar",
            4:    "Fataler Fehler",
            5:    "Nicht implementiert",
            6:    "Timeout",
            8:    "Abgebrochen",
            16:   "System beschäftigt",
            17:   "Hardware-Fehler",
            32:   "Niedriger Akkustand",
            36:   "Akku leer",
            52:   "Instrument bewegt sich",
            56:   "GeoCOM nicht verfügbar",
            1283: "Warnung: Nicht alle Korrekturen aktiv",
            1284: "Warnung: Winkel ohne vollständige Korrektur",
            1285: "Winkel OK (Distanz nicht gemessen)",
            1288: "Warnung: Genauigkeit nicht garantiert",
            1289: "Distanz mit PPM-Korrektur",
            1290: "Distanzfehler",
            1291: "Winkelfehler",
            1292: "Keine Distanz gemessen",
        }
        return descriptions.get(rc, f"Unbekannter Code: {rc}")


# ─────────────────────────────────────────────
# Remote Procedure Codes (RPC) — Befehlsnummern
# ─────────────────────────────────────────────
class RPC:
    """GeoCOM Remote Procedure Codes (Befehlsnummern)."""

    # COM — Kommunikation
    COM_GET_SW_VERSION   = 5003   # Firmware-Version abfragen
    COM_NULLPROC         = 0      # Verbindungstest (Ping)
    COM_SWITCH_OFF       = 5005   # Instrument ausschalten

    # EDM — Distanzmessung
    EDM_LAPON            = 1004   # Laser einschalten
    EDM_LAPOFF           = 1005   # Laser ausschalten

    # TMC — Messung und Berechnung
    TMC_DO_MEASURE       = 2008   # Messung auslösen
    TMC_GET_COORDINATE   = 2082   # Koordinaten abfragen (X, Y, Z)
    TMC_GET_SIMPLE_MEA   = 2108   # Einfache Messung (Hz, V, Distanz)
    TMC_QUICK_DIST       = 2117   # Schnelle Distanzmessung
    TMC_SET_EDM_MODE     = 2020   # EDM-Modus setzen

    # BAP — Basic Applications
    BAP_MEASURE_DIST_ANGLE = 17017  # Distanz + Winkel messen
    BAP_GET_MEAS_PRG     = 17018  # Messprogramm abfragen

    # AUS — Automatische Suche / ATR
    AUS_SET_USER_ATR_STATE = 18005  # ATR-Status setzen

    # AUT — Automatisierung
    AUT_LOCK_IN          = 9013   # Prisma einschließen
    AUT_SEARCH           = 9029   # Prisma suchen

    # CSV — Instrument-Informationen
    CSV_GET_INSTRUMENT_NO = 5003  # Seriennummer (= COM_GET_SW_VERSION)
    CSV_GET_INSTRUMENT_NAME = 5004  # Instrumentenname


# ─────────────────────────────────────────────
# TMC Messmodi
# ─────────────────────────────────────────────
class TMC_MODE:
    """Modi für TMC_DO_MEASURE."""
    STOP         = 0   # Messung stoppen
    DEF_DIST     = 1   # Standard-Distanzmessung (mit Prisma)
    CLEAR        = 3   # Messung löschen
    SIGNAL       = 4   # Signalstärke messen
    DO_MEASURE   = 6   # Messung durchführen
    RTRK_DIST    = 8   # Schnelle Tracking-Messung
    RED_TRK_DIST = 10  # Reduzierte Tracking-Messung
    REFLLESS     = 11  # Reflektorlos (für TS07 ohne Prisma!)


# ─────────────────────────────────────────────
# GeoCOM-Befehl-Builder
# ─────────────────────────────────────────────
def build_request(rpc: int, *params) -> str:
    """
    Erstellt einen GeoCOM-Request-String.

    Beispiel:
      build_request(RPC.COM_GET_SW_VERSION)  → "%R1Q,5003:\\r\\n"
      build_request(RPC.TMC_DO_MEASURE, 11, 1) → "%R1Q,2008:11,1\\r\\n"
    """
    param_str = ",".join(str(p) for p in params)
    return f"%R1Q,{rpc}:{param_str}\r\n"


def parse_response(raw: str) -> dict:
    """
    Parst eine GeoCOM-Antwort in ein Dict.

    Eingabe:  "%R1P,0,0:0,1.234,5.678,9.012"
    Ausgabe:  {"rc": 0, "values": [1.234, 5.678, 9.012], "raw": "..."}

    rc=0 bedeutet Erfolg. Andere Werte: RC.describe(rc) aufrufen.
    """
    raw = raw.strip()
    result = {"rc": -1, "values": [], "raw": raw}

    try:
        # Format: %R1P,0,<trans>:<rc>,<val1>,<val2>,...
        if not raw.startswith("%R1P"):
            return result

        colon_idx = raw.index(":")
        after_colon = raw[colon_idx + 1:]
        parts = after_colon.split(",")

        rc = int(parts[0])
        values = []
        for p in parts[1:]:
            p = p.strip()
            if not p:
                continue
            try:
                # Versuche zuerst int, dann float
                if "." in p:
                    values.append(float(p))
                else:
                    values.append(int(p))
            except ValueError:
                values.append(p)  # String-Wert behalten

        result["rc"] = rc
        result["values"] = values

    except (ValueError, IndexError) as e:
        result["error"] = str(e)

    return result
