#!/usr/bin/env bash
# Weather grid refresh — run every 3-6 hours via cron:
#   0 */3 * * * /Users/arjunpol/FireRAG/refresh_weather.sh
set -euo pipefail

cd "$(dirname "$0")"

LOG="logs/weather_$(date +%Y%m%d_%H%M).log"
mkdir -p logs

exec >> "$LOG" 2>&1
echo "=== $(date -u '+%Y-%m-%d %H:%M:%S UTC') ==="

source .env 2>/dev/null || true

echo "Fetching NWS current conditions grid..."
python3 -m weather.fetch_grid --spacing 1.0 --workers 5

echo "Fetching NWS 7-day forecast..."
python3 -m weather.fetch_forecast --workers 5

echo "Recomputing risk forecast grid..."
python3 -m risk.compute_risk

echo "Done."
