#!/usr/bin/env bash
# Daily FIRMS refresh: fetch new detections → rebuild RAG index → export map JSON
set -euo pipefail

cd "$(dirname "$0")"

LOG="logs/refresh_$(date +%Y%m%d).log"
mkdir -p logs

exec >> "$LOG" 2>&1
echo "=== $(date -u '+%Y-%m-%d %H:%M:%S UTC') ==="

source .env 2>/dev/null || true

echo "[1/3] Fetching FIRMS data..."
python3 ingest.py

echo "[2/3] Rebuilding FIRMS RAG index..."
python3 -m rag.build_firms_index

echo "[3/3] Exporting fires.json..."
python3 export_data.py

echo "Done."
