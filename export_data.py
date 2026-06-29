#!/usr/bin/env python3
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def export_fires(db_path: str = "firerag.db", out_path: str = "app/public/fires.json") -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    latest = conn.execute(
        "SELECT prediction_date FROM fires_predictions ORDER BY prediction_date DESC LIMIT 1"
    ).fetchone()

    if latest:
        pred_date = latest["prediction_date"]
        rows = conn.execute("""
            WITH deduped AS (
                SELECT
                    round(latitude  * 2) / 2 AS bin_lat,
                    round(longitude * 2) / 2 AS bin_lon,
                    MAX(fire_probability)     AS fire_probability
                FROM fires_predictions
                WHERE prediction_date = ?
                GROUP BY bin_lat, bin_lon
            )
            SELECT
                f.id,
                f.latitude,
                f.longitude,
                f.brightness,
                f.acq_date,
                f.acq_time,
                f.confidence,
                f.satellite,
                d.fire_probability
            FROM fires_realtime f
            LEFT JOIN deduped d
                ON round(f.latitude  * 2) / 2 = d.bin_lat
               AND round(f.longitude * 2) / 2 = d.bin_lon
        """, (pred_date,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, latitude, longitude, brightness, acq_date, acq_time,
                   confidence, satellite, NULL AS fire_probability
            FROM fires_realtime
        """).fetchall()

    conn.close()

    fires = [
        {
            "id": r["id"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "brightness": r["brightness"],
            "acq_date": r["acq_date"],
            "acq_time": r["acq_time"],
            "confidence": r["confidence"],
            "satellite": r["satellite"],
            "fire_probability": r["fire_probability"],
        }
        for r in rows
    ]

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(fires),
        "fires": fires,
    }, indent=2))

    print(f"Wrote {len(fires)} fires to {out_path}")
    return len(fires)


def main():
    parser = argparse.ArgumentParser(description="Export fires from firerag.db to JSON")
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--out", default="app/public/fires.json")
    args = parser.parse_args()
    export_fires(db_path=args.db, out_path=args.out)


if __name__ == "__main__":
    main()
