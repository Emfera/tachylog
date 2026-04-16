"""
tachylog CLI

Befehle:
  tachylog collect  --port tcp://localhost:4444 --db feld.db
  tachylog collect  --port tcp://localhost:4444 --csv feld.csv --gsi feld.gsi
  tachylog collect  --port tcp://localhost:4444 --db feld.db --csv feld.csv --gsi feld.gsi --geojson feld.geojson
  tachylog import   punkte.csv --db feld.db
  tachylog build    feld.db ausgabe.gpkg
  tachylog info     feld.db
  tachylog validate feld.db
  tachylog codes
"""

import click
import logging

from .connection import ConnectionConfig
from .collector import run_collector, CollectorConfig
from .csv_collector import import_csv
from .feature_builder import build_geopackage
from .staging import StagingDB
from .code_table import CODE_TABLE
from .pid_parser import validate_pid_sequence


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
              help="CSV-Ausgabe, Emlid Flow kompatibel (z.B. aufnahme.csv)")
@click.option("--gsi", "gsi_path", default=None,
              help="GSI-Rohausgabe, exakt wie vom Instrument (z.B. aufnahme.gsi)")
@click.option("--geojson", "geojson_path", default=None,
              help="GeoJSON-Ausgabe für QGIS/Web (z.B. aufnahme.geojson)")
@click.option("--interval", default=0.5, show_default=True,
              help="Polling-Intervall in Sekunden")
def collect(port, db, csv_path, gsi_path, geojson_path, interval):
    """Empfängt Messungen vom TS07 und speichert in gewählten Formaten.

    Mindestens ein Ausgabeformat muss angegeben werden.
    Mehrere Formate gleichzeitig sind möglich.

    Beispiele:

      tachylog collect --db aufnahme.db

      tachylog collect --csv aufnahme.csv --gsi aufnahme.gsi

      tachylog collect --db aufnahme.db --csv aufnahme.csv --geojson aufnahme.geojson
    """
    # Wenn nichts angegeben: Standard ist SQLite
    if not any([db, csv_path, gsi_path, geojson_path]):
        db = "tachylog.db"
        click.echo(f"  Kein Ausgabeformat angegeben — verwende Standard: {db}")

    conn_config = ConnectionConfig(port=port, timeout=0.5)
    run_collector(
        conn_config,
        db_path=db,
        poll_interval=interval,
        csv_path=csv_path,
        gsi_path=gsi_path,
        geojson_path=geojson_path,
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
    count = import_csv(csv_file, db, delimiter=delimiter)
    click.echo(f"✓ {count} Punkte importiert aus '{csv_file}'")


# ── build ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("db_file", type=click.Path(exists=True))
@click.argument("output", default="ausgabe.gpkg")
@click.option("--crs", default=4326, show_default=True,
              help="Koordinatenreferenzsystem (EPSG-Code)")
def build(db_file, output, crs):
    """Baut ein GeoPackage (.gpkg) aus der Staging-Datenbank."""
    db = StagingDB(db_file)
    points = db.get_all_points()
    if not points:
        click.echo("✗ Keine Punkte in der Datenbank.")
        return
    result = build_geopackage(points, output, crs=crs)
    click.echo(f"✓ GeoPackage erstellt: {output}")
    click.echo(f"  Punkte:   {result.get('points', 0)}")
    click.echo(f"  Linien:   {result.get('lines', 0)}")
    click.echo(f"  Flächen:  {result.get('polygons', 0)}")


# ── info ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("db_file", type=click.Path(exists=True))
def info(db_file):
    """Zeigt Statistiken über die Staging-Datenbank."""
    db = StagingDB(db_file)
    points = db.get_all_points()
    if not points:
        click.echo("Keine Punkte in der Datenbank.")
        return

    from collections import Counter
    sources = Counter(p.source for p in points)

    click.echo(f"\n  Datenbank: {db_file}")
    click.echo(f"  Punkte gesamt: {len(points)}\n")
    click.echo("  Nach Quelle:")
    for source, count in sorted(sources.items()):
        click.echo(f"    {source:<20} {count}")
    click.echo()


# ── validate ──────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("db_file", type=click.Path(exists=True))
def validate(db_file):
    """Prüft PID-Sequenzen auf Lücken oder Fehler."""
    db = StagingDB(db_file)
    points = db.get_all_points()
    pids = [p.pid for p in points]
    issues = validate_pid_sequence(pids)
    if not issues:
        click.echo("✓ Alle PID-Sequenzen vollständig.")
    else:
        click.echo(f"✗ {len(issues)} Problem(e) gefunden:\n")
        for issue in issues:
            click.echo(f"  • {issue}")


# ── codes ─────────────────────────────────────────────────────────────────────

@cli.command()
def codes():
    """Zeigt alle verfügbaren Vermessungs-Codes."""
    click.echo("\n  Code  Typ       Deutsch              Englisch")
    click.echo("  " + "─" * 55)
    for code, info in sorted(CODE_TABLE.items()):
        geom = info.get("geometry", "?")
        name_de = info.get("name_de", "")
        name_en = info.get("name_en", "")
        geom_sym = {"point": "Punkt  ", "line": "Linie  ", "polygon": "Fläche "}.get(geom, "?      ")
        click.echo(f"  {code}    {geom_sym}  {name_de:<20} {name_en}")
    click.echo()
