"""
tachylog CLI

Befehle:
  tachylog collect  --port tcp://localhost:4444 --db feld.db
  tachylog collect  --port tcp://localhost:4444 --csv feld.csv --gsi feld.gsi
  tachylog collect  --port tcp://localhost:4444 --db feld.db --schema schemas/gladiator2.json
  tachylog import   punkte.csv --db feld.db
  tachylog info     feld.db
  tachylog validate feld.db --schema schemas/gladiator2.json
  tachylog schemas
"""

import click
import logging
from pathlib import Path

from .connection import ConnectionConfig
from .collector import run_collector
from .csv_collector import import_csv
from .staging import StagingDB
from .schema_validator import SchemaDef


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Detailliertes Logging")
def cli(verbose):
    """tachylog — GSI-Datenlogger für Leica Flexline Totalstationen"""
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)


# ── collect ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--port", default="tcp://localhost:4444",
              show_default=True,
              help="Verbindungsport: tcp://localhost:4444 (Android)")
@click.option("--db", default=None,
              help="SQLite-Datenbank (z.B. aufnahme.db)")
@click.option("--csv", "csv_path", default=None,
              help="CSV-Ausgabe (z.B. aufnahme.csv)")
@click.option("--gsi", "gsi_path", default=None,
              help="GSI-Rohausgabe (z.B. aufnahme.gsi)")
@click.option("--geojson", "geojson_path", default=None,
              help="GeoJSON-Ausgabe (z.B. aufnahme.geojson)")
@click.option("--schema", "schema_path", default=None,
              help="Optionales Schema für Gültigkeitsprüfung (z.B. schemas/gladiator2.json)")
@click.option("--interval", default=0.2, show_default=True,
              help="Polling-Intervall in Sekunden (Default: 0.2 = 5 Hz)")
@click.option("--epsg", "epsg_code", default=31256, show_default=True,
              help="EPSG-Code des Koordinatensystems (Metadaten, keine Transformation). "
                   "AT: 31256=M31 (Standard), 31255=M28, 31257=M34")
def collect(port, db, csv_path, gsi_path, geojson_path, schema_path, interval, epsg_code):
    """Empfängt Messungen vom TS07 und speichert in gewählten Formaten.

    Mindestens ein Ausgabeformat muss angegeben werden.
    Mehrere Formate gleichzeitig sind möglich.

    Beispiele:

      tachylog collect --db aufnahme.db

      tachylog collect --csv aufnahme.csv --gsi aufnahme.gsi

      tachylog collect --db aufnahme.db --schema schemas/gladiator2.json
    """
    if not any([db, csv_path, gsi_path, geojson_path]):
        db = "tachylog.db"
        click.echo(f"  Kein Ausgabeformat angegeben — verwende Standard: {db}")

    # Schema laden
    if schema_path:
        try:
            schema = SchemaDef.load(schema_path)
            click.echo(f"  Schema: {schema.summary()}")
        except (FileNotFoundError, KeyError, ValueError) as e:
            click.echo(f"  [WARN] Schema konnte nicht geladen werden: {e} — fahre ohne Schema fort")
            schema = SchemaDef.free()
    else:
        schema = SchemaDef.free()

    conn_config = ConnectionConfig(port=port, timeout=0.5)
    run_collector(
        conn_config,
        db_path=db,
        poll_interval=interval,
        csv_path=csv_path,
        gsi_path=gsi_path,
        geojson_path=geojson_path,
        schema=schema,
        epsg_code=epsg_code,
    )


# ── import ────────────────────────────────────────────────────────────────────

@cli.command("import")
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--db", default="tachylog.db", show_default=True,
              help="Pfad zur Staging-Datenbank")
@click.option("--delimiter", default=",", show_default=True,
              help="CSV-Trennzeichen")
def import_cmd(csv_file, db, delimiter):
    """Importiert eine GNSS-CSV-Datei in die Staging-Datenbank."""
    staging = StagingDB(db)
    result = import_csv(staging, csv_file, delimiter=delimiter)
    click.echo(f"✓ {result['imported']} Punkte importiert aus '{csv_file}'")
    if result.get("errors"):
        for e in result["errors"][:5]:
            click.echo(f"  [WARN] {e}")


# ── info ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("db_file", type=click.Path(exists=True))
def info(db_file):
    """Zeigt Statistiken über die Staging-Datenbank."""
    db = StagingDB(db_file)
    stats = db.get_stats()

    click.echo(f"\n  Datenbank: {db_file}")
    click.echo(f"  Punkte gesamt: {stats['total']}")
    click.echo(f"    TS07 (geocom): {stats.get('geocom', 0)}")
    click.echo(f"    GNSS (gnss):   {stats.get('gnss', 0)}")
    click.echo()


# ── validate ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("db_file", type=click.Path(exists=True))
@click.option("--schema", "schema_path", required=True,
              help="Schema-Datei für die Prüfung (z.B. schemas/gladiator2.json)")
def validate(db_file, schema_path):
    """Prüft alle PIDs in der Datenbank gegen ein Schema.

    Nützlich als Post-hoc-Check vor dem Export.

    Beispiel:

      tachylog validate aufnahme.db --schema schemas/gladiator2.json
    """
    try:
        schema = SchemaDef.load(schema_path)
    except (FileNotFoundError, KeyError, ValueError) as e:
        click.echo(f"✗ Schema konnte nicht geladen werden: {e}")
        return

    db = StagingDB(db_file)
    points = db.get_all_points()

    if not points:
        click.echo("Keine Punkte in der Datenbank.")
        return

    click.echo(f"\n  Schema: {schema.summary()}")
    click.echo(f"  Punkte: {len(points)}\n")

    issues: list[tuple] = []
    for pt in points:
        warnings = schema.validate(pt.pid)
        for w in warnings:
            issues.append((pt.pid, w))

    if not issues:
        click.echo(f"  ✓ Alle {len(points)} PIDs entsprechen dem Schema '{schema.name}'.")
    else:
        click.echo(f"  ✗ {len(issues)} Warnung(en) gefunden:\n")
        shown = set()
        for pid, msg in issues:
            if msg not in shown:
                click.echo(f"    • {msg}")
                shown.add(msg)
        click.echo()


# ── schemas ───────────────────────────────────────────────────────────────────

@cli.command("schemas")
def list_schemas():
    """Zeigt alle verfügbaren Schema-Dateien."""
    schema_dir = Path(__file__).parent / "schemas"
    files = sorted(schema_dir.glob("*.json"))

    if not files:
        click.echo("Keine Schema-Dateien gefunden.")
        return

    click.echo(f"\n  Verfügbare Schemata ({schema_dir}):\n")
    for f in files:
        try:
            s = SchemaDef.load(f)
            marker = "  →" if s.name != "free" else "  ·"
            click.echo(f"{marker} {f.name:<25} {s.summary()}")
        except Exception as e:
            click.echo(f"  ✗ {f.name}: {e}")
    click.echo()
