"""Load confirmed wildfire perimeters from GeoMAC, IFPH, and WFIGS into SQLite."""
import argparse
import csv
import json
import os
import sqlite3
from datetime import datetime

GEOMAC_FILE = "Historic_Geomac_Perimeters_Combined_2000_2018_-6243522490534825338.geojson"
IFPH_FILE = "InterAgencyFirePerimeterHistory_All_Years_View_-7109815838341171365.csv"
WFIGS_FILE = "WFIGS_Interagency_Perimeters_-8730464049412665158.geojson"

_DDL = """
CREATE TABLE IF NOT EXISTS fire_perimeters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fire_name     TEXT,
    fire_year     INTEGER,
    state         TEXT,
    acres         REAL,
    agency        TEXT,
    discovery_date TEXT,
    cause         TEXT,
    latitude      REAL,
    longitude     REAL,
    irwin_id      TEXT UNIQUE,
    source        TEXT
)
"""


def _centroid(geometry):
    if geometry is None:
        return None, None
    gtype = geometry.get("type")
    if gtype == "Polygon":
        coords = geometry["coordinates"][0]
    elif gtype == "MultiPolygon":
        coords = [c for ring in geometry["coordinates"] for c in ring[0]]
    else:
        return None, None
    if not coords:
        return None, None
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def _parse_date(s):
    if not s:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            continue
    return str(s)[:10] if s else None


def load_geomac(conn, base_dir):
    path = os.path.join(base_dir, GEOMAC_FILE)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for feat in data["features"]:
        p = feat["properties"]
        acres = p.get("gisacres") or 0
        if acres < 10:
            continue
        irwin = (p.get("irwinid") or "").strip().lower() or None
        lat, lon = _centroid(feat.get("geometry"))
        try:
            conn.execute(
                """INSERT OR IGNORE INTO fire_perimeters
                   (fire_name, fire_year, state, acres, agency, discovery_date, cause, latitude, longitude, irwin_id, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    (p.get("incidentname") or "").title(),
                    p.get("fireyear"),
                    p.get("state"),
                    round(acres, 1),
                    p.get("agency"),
                    _parse_date(p.get("perimeterdatetime")),
                    None,
                    lat,
                    lon,
                    irwin,
                    "geomac",
                ),
            )
            count += conn.execute("SELECT changes()").fetchone()[0]
        except Exception:
            continue
    conn.commit()
    return count


def load_ifph(conn, base_dir):
    path = os.path.join(base_dir, IFPH_FILE)
    count = 0
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "Final" not in (row.get("FEATURE_CA") or ""):
                continue
            try:
                acres = float(row.get("GIS_ACRES") or 0)
            except ValueError:
                acres = 0
            if acres < 10:
                continue
            unit = (row.get("UNIT_ID") or "")
            state = unit[:2].upper() if len(unit) >= 2 else None
            irwin = (row.get("IRWINID") or "").strip().strip("{}").lower() or None
            date_raw = row.get("DATE_CUR") or ""
            discovery = _parse_date(date_raw) if date_raw else None
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO fire_perimeters
                       (fire_name, fire_year, state, acres, agency, discovery_date, cause, latitude, longitude, irwin_id, source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        (row.get("INCIDENT") or "").title(),
                        int(row["FIRE_YEAR"]) if row.get("FIRE_YEAR") else None,
                        state,
                        round(acres, 1),
                        row.get("AGENCY"),
                        discovery,
                        None,
                        None,
                        None,
                        irwin,
                        "ifph",
                    ),
                )
                count += conn.execute("SELECT changes()").fetchone()[0]
            except Exception:
                continue
    conn.commit()
    return count


def load_wfigs(conn, base_dir):
    path = os.path.join(base_dir, WFIGS_FILE)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for feat in data["features"]:
        p = feat["properties"]
        if (p.get("poly_FeatureCategory") or "") not in (
            "Wildfire Final Fire Perimeter", None
        ):
            continue
        acres = p.get("poly_GISAcres") or p.get("attr_FinalAcres") or 0
        try:
            acres = float(acres)
        except (TypeError, ValueError):
            acres = 0
        if acres < 10:
            continue
        state_raw = p.get("attr_POOState") or ""
        state = state_raw.split("-")[-1] if "-" in state_raw else state_raw or None
        irwin = (p.get("attr_IrwinID") or "").strip().strip("{}").lower() or None
        lat = p.get("attr_InitialLatitude")
        lon = p.get("attr_InitialLongitude")
        if not lat or not lon:
            lat, lon = _centroid(feat.get("geometry"))
        cause = p.get("attr_FireCauseGeneral") or p.get("attr_FireCause")
        try:
            conn.execute(
                """INSERT OR IGNORE INTO fire_perimeters
                   (fire_name, fire_year, state, acres, agency, discovery_date, cause, latitude, longitude, irwin_id, source)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    (p.get("attr_IncidentName") or "").title(),
                    None,
                    state,
                    round(float(acres), 1),
                    None,
                    _parse_date(p.get("attr_FireDiscoveryDateTime")),
                    cause,
                    lat,
                    lon,
                    irwin,
                    "wfigs",
                ),
            )
            count += conn.execute("SELECT changes()").fetchone()[0]
        except Exception:
            continue
    conn.commit()
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--data-dir", default=".")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute(_DDL)
    conn.commit()

    n1 = load_geomac(conn, args.data_dir)
    print(f"GeoMAC:  {n1} fires loaded")
    n2 = load_ifph(conn, args.data_dir)
    print(f"IFPH:    {n2} fires loaded")
    n3 = load_wfigs(conn, args.data_dir)
    print(f"WFIGS:   {n3} fires loaded")

    total = conn.execute("SELECT COUNT(*) FROM fire_perimeters").fetchone()[0]
    print(f"Total:   {total} confirmed fires in database")
    conn.close()


if __name__ == "__main__":
    main()
