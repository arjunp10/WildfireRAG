"""Export confirmed fire perimeter data for the map."""
import json
import sqlite3

_MONTH_NAMES = {
    'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
    'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12
}

def _month_idx(year, month):
    """Encode year+month as months since Jan 2000."""
    if not year or not month:
        return None
    return (year - 2000) * 12 + (month - 1)

def _parse_month_from_str(s):
    """Parse month from 'Fri, 07 Jul 2017 14:00:00 GMT' → (2017, 7)."""
    if not s:
        return None, None
    parts = s.split()
    try:
        month = _MONTH_NAMES.get(parts[2])
        year = int(parts[3])
        return year, month
    except (IndexError, ValueError):
        return None, None


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
            CAST(substr(discovery_date,6,2) AS INTEGER) as mo,
            state,
            acres,
            latitude,
            longitude
        FROM fire_perimeters
        WHERE acres >= ? AND latitude IS NOT NULL AND longitude IS NOT NULL
        AND COALESCE(fire_year, CAST(substr(discovery_date,1,4) AS INTEGER)) BETWEEN 2000 AND 2026
    """, (DOTS_MIN_ACRES,)).fetchall()

    features = []
    for name, year, mo, state, acres, lat, lon in rows:
        midx = _month_idx(year, mo)
        props = {
            "name": name or "Unknown",
            "year": year,
            "state": state,
            "acres": round(acres, 0),
        }
        if midx is not None:
            props["month_idx"] = midx
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
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
        date_str = p.get("perimeterdatetime") or ""
        gy, gmo = _parse_month_from_str(date_str)
        if not gy:
            gy = year
        midx = _month_idx(gy, gmo)
        props = {
            "name": (p.get("incidentname") or "").title(),
            "year": year,
            "state": p.get("state"),
            "acres": round(float(acres), 0),
        }
        if midx is not None:
            props["month_idx"] = midx
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
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
        wdate = p.get("attr_FireDiscoveryDateTime") or ""
        wy, wmo = _parse_month_from_str(wdate)
        if not wy:
            wy = year
        midx = _month_idx(wy, wmo)
        props = {
            "name": (p.get("attr_IncidentName") or "").title(),
            "year": year,
            "state": (p.get("attr_POOState") or "").split("-")[-1] or None,
            "acres": round(acres, 0),
        }
        if midx is not None:
            props["month_idx"] = midx
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
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
