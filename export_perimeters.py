"""Export confirmed fire perimeter data for the map."""
import json
import sqlite3


GEOMAC_FILE = "Historic_Geomac_Perimeters_Combined_2000_2018_-6243522490534825338.geojson"
WFIGS_FILE = "WFIGS_Interagency_Perimeters_-8730464049412665158.geojson"

DOTS_OUT = "app/public/perimeter_dots.json"
OUTLINES_OUT = "app/public/perimeter_outlines.json"

DOTS_MIN_ACRES = 100
OUTLINE_MIN_ACRES = 50000
MAX_RING_POINTS = 80  # simplify polygons for web display


def _simplify_ring(coords):
    """Keep at most MAX_RING_POINTS by uniform decimation."""
    if len(coords) <= MAX_RING_POINTS:
        return coords
    step = max(1, len(coords) // MAX_RING_POINTS)
    simplified = coords[::step]
    if simplified[-1] != coords[-1]:
        simplified.append(coords[-1])
    return simplified


def _simplify_geometry(geometry):
    if geometry is None:
        return None
    if geometry["type"] == "Polygon":
        return {
            "type": "Polygon",
            "coordinates": [_simplify_ring(geometry["coordinates"][0])]
            + geometry["coordinates"][1:],
        }
    elif geometry["type"] == "MultiPolygon":
        return {
            "type": "MultiPolygon",
            "coordinates": [
                [_simplify_ring(ring) for ring in poly]
                for poly in geometry["coordinates"]
            ],
        }
    return geometry


def export_dots(conn):
    rows = conn.execute("""
        SELECT
            fire_name,
            COALESCE(fire_year, CAST(substr(discovery_date,1,4) AS INTEGER)) as yr,
            state,
            acres,
            latitude,
            longitude,
            source
        FROM fire_perimeters
        WHERE acres >= ? AND latitude IS NOT NULL AND longitude IS NOT NULL
        AND COALESCE(fire_year, CAST(substr(discovery_date,1,4) AS INTEGER)) BETWEEN 2000 AND 2026
    """, (DOTS_MIN_ACRES,)).fetchall()

    features = []
    for name, year, state, acres, lat, lon, source in rows:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "name": name or "Unknown",
                "year": year,
                "state": state,
                "acres": round(acres, 0),
            },
        })

    out = {"type": "FeatureCollection", "features": features}
    with open(DOTS_OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"Dots: {len(features)} fires → {DOTS_OUT}")


def export_outlines():
    features = []

    # GeoMAC
    print("Reading GeoMAC polygons...")
    with open(GEOMAC_FILE, encoding="utf-8") as f:
        geomac = json.load(f)
    for feat in geomac["features"]:
        p = feat["properties"]
        acres = p.get("gisacres") or 0
        year = p.get("fireyear")
        if not year or not isinstance(year, int):
            continue
        if acres < OUTLINE_MIN_ACRES or not (2000 <= year <= 2026):
            continue
        geom = _simplify_geometry(feat.get("geometry"))
        if geom is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": (p.get("incidentname") or "").title(),
                "year": year,
                "state": p.get("state"),
                "acres": round(float(acres), 0),
            },
        })

    # WFIGS
    print("Reading WFIGS polygons...")
    with open(WFIGS_FILE, encoding="utf-8") as f:
        wfigs = json.load(f)
    for feat in wfigs["features"]:
        p = feat["properties"]
        if (p.get("poly_FeatureCategory") or "") not in (
            "Wildfire Final Fire Perimeter", None
        ):
            continue
        acres = p.get("poly_GISAcres") or p.get("attr_FinalAcres") or 0
        try:
            acres = float(acres)
        except (TypeError, ValueError):
            continue
        if acres < OUTLINE_MIN_ACRES:
            continue
        date_str = p.get("attr_FireDiscoveryDateTime") or ""
        year = None
        for part in date_str.split():
            if len(part) == 4 and part.isdigit():
                year = int(part)
                break
        if not year or not (2000 <= year <= 2026):
            continue
        geom = _simplify_geometry(feat.get("geometry"))
        if geom is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "name": (p.get("attr_IncidentName") or "").title(),
                "year": year,
                "state": (p.get("attr_POOState") or "").split("-")[-1] or None,
                "acres": round(acres, 0),
            },
        })

    out = {"type": "FeatureCollection", "features": features}
    with open(OUTLINES_OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    size_mb = len(json.dumps(out)) / 1e6
    print(f"Outlines: {len(features)} fires ({size_mb:.1f} MB) → {OUTLINES_OUT}")


if __name__ == "__main__":
    conn = sqlite3.connect("firerag.db")
    export_dots(conn)
    conn.close()
    export_outlines()
