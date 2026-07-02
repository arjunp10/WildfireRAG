"""
Active fire spread prediction (Option C).

For each cluster of recent FIRMS detections:
  1. Compute cluster centroid and detection count.
  2. Look up the nearest weather grid point for wind direction + FWI.
  3. Project a 24-hour spread ellipse aligned with the downwind direction.
     Major axis (downwind): driven by wind speed and FWI.
     Minor axis (crosswind): 35% of major axis.

Spread distance formula (km in 24h):
  base        = 3 km  (fire already burning)
  fwi_contrib = FWI * 1.2
  wind_contrib = wind_mph * 1.5
  major_km    = base + fwi_contrib + wind_contrib  (capped at 150 km)

Returns a GeoJSON FeatureCollection of spread ellipses.
"""
import math
import sqlite3
from collections import defaultdict

DB_PATH = "firerag.db"

# Cluster fires within this many degrees of each other into one group
CLUSTER_RADIUS_DEG = 0.4
MIN_DETECTIONS = 3     # ignore tiny single-pixel clusters
MAX_CLUSTERS   = 25    # cap to avoid overwhelming the map
ELLIPSE_POINTS = 48    # polygon resolution


def _nearest_weather(conn, lat: float, lon: float) -> dict | None:
    """Find the closest weather_grid row to (lat, lon) using simple L2 distance."""
    row = conn.execute("""
        SELECT lat, lon, wind_speed_mph, wind_dir_deg,
               COALESCE(forecast_fwi, fosberg_index) AS fwi
        FROM weather_grid
        WHERE fetched_at IS NOT NULL
        ORDER BY ((lat - ?) * (lat - ?)) + ((lon - ?) * (lon - ?))
        LIMIT 1
    """, (lat, lat, lon, lon)).fetchone()
    return dict(row) if row else None


def _spread_ellipse(
    center_lat: float, center_lon: float,
    wind_dir_deg: float, wind_mph: float, fwi: float,
) -> dict:
    """
    Build a GeoJSON Polygon approximating the 24-hour fire spread zone.
    wind_dir_deg: meteorological convention (direction wind comes FROM).
    Fire spreads in the OPPOSITE direction (downwind).
    """
    # Downwind direction (where fire travels)
    spread_dir_rad = math.radians((wind_dir_deg + 180) % 360)

    # Spread extent
    base      = 3.0
    fwi_km    = min(fwi, 40) * 1.2
    wind_km   = wind_mph * 1.5
    major_km  = min(base + fwi_km + wind_km, 150.0)
    minor_km  = major_km * 0.35

    # km → degrees conversion at this latitude
    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * math.cos(math.radians(center_lat))

    coords = []
    for i in range(ELLIPSE_POINTS + 1):
        theta = 2 * math.pi * i / ELLIPSE_POINTS
        # Ellipse in spread-frame coordinates
        along = (major_km / 2) * math.cos(theta)  # along wind axis
        cross = (minor_km / 2) * math.sin(theta)  # crosswind

        # Rotate into geographic frame
        # spread_dir_rad is the bearing of downwind direction (clockwise from N)
        dx_km =  along * math.sin(spread_dir_rad) - cross * math.cos(spread_dir_rad)
        dy_km =  along * math.cos(spread_dir_rad) + cross * math.sin(spread_dir_rad)

        lon = center_lon + dx_km / km_per_deg_lon
        lat = center_lat + dy_km / km_per_deg_lat
        coords.append([lon, lat])

    return {"type": "Polygon", "coordinates": [coords]}


def get_spread_geojson(db_path: str = DB_PATH, days_back: int = 3) -> dict:
    """
    Return a GeoJSON FeatureCollection of spread ellipses for active fire clusters.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    fires = conn.execute(f"""
        SELECT latitude, longitude, brightness, confidence
        FROM fires_realtime
        WHERE acq_date >= date('now', '-{days_back} days')
          AND confidence IN ('h', 'n')
        ORDER BY acq_date DESC
    """).fetchall()

    if not fires:
        conn.close()
        return {"type": "FeatureCollection", "features": []}

    # Simple grid clustering: round to CLUSTER_RADIUS_DEG grid
    clusters: dict[tuple, list] = defaultdict(list)
    for f in fires:
        cell = (
            round(f["latitude"]  / CLUSTER_RADIUS_DEG) * CLUSTER_RADIUS_DEG,
            round(f["longitude"] / CLUSTER_RADIUS_DEG) * CLUSTER_RADIUS_DEG,
        )
        clusters[cell].append(f)

    # Sort by detection count, take top N
    sorted_clusters = sorted(clusters.values(), key=len, reverse=True)[:MAX_CLUSTERS]

    features = []
    for detections in sorted_clusters:
        if len(detections) < MIN_DETECTIONS:
            continue

        center_lat = sum(d["latitude"]  for d in detections) / len(detections)
        center_lon = sum(d["longitude"] for d in detections) / len(detections)
        avg_brightness = sum(d["brightness"] or 0 for d in detections) / len(detections)

        wx = _nearest_weather(conn, center_lat, center_lon)
        if not wx:
            continue

        wind_dir = wx["wind_dir_deg"] or 0.0
        wind_mph = wx["wind_speed_mph"] or 0.0
        fwi      = wx["fwi"] or 0.0

        geom = _spread_ellipse(center_lat, center_lon, wind_dir, wind_mph, fwi)

        major_km = min(3.0 + min(fwi, 40) * 1.2 + wind_mph * 1.5, 150.0)

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "detections":  len(detections),
                "brightness":  round(avg_brightness, 1),
                "wind_dir":    round(wind_dir, 0),
                "wind_mph":    round(wind_mph, 1),
                "fwi":         round(fwi, 1),
                "spread_km":   round(major_km, 1),
                "center_lat":  round(center_lat, 3),
                "center_lon":  round(center_lon, 3),
            },
        })

    conn.close()
    return {"type": "FeatureCollection", "features": features}


if __name__ == "__main__":
    import json
    result = get_spread_geojson()
    print(f"{len(result['features'])} spread ellipses")
    if result["features"]:
        p = result["features"][0]["properties"]
        print(f"  Largest cluster: {p['detections']} detections, {p['spread_km']}km spread, wind {p['wind_mph']}mph from {p['wind_dir']}°")
