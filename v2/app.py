"""
GreenRoute Mesh v2 — API Server

POST /api/ingest    — ESP32 sends raw sensor JSON → stored in raw_telemetry
POST /api/process   — manually trigger processing of pending rows
GET  /api/readings  — latest processed readings
GET  /api/stats     — quick summary counts
GET  /api/health    — health-check

Background worker runs every PROCESS_INTERVAL seconds (default 25 s),
picks up all unprocessed raw_telemetry rows, runs the processor, and
writes enriched rows into processed_data.
"""

import os
import sys
import logging
import threading
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

# Allow imports from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_client import db
from processor import processor

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-22s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("greenroute.api")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)


# =============================================================================
#  POST /api/ingest  — ESP32 raw data → Supabase raw_telemetry
# =============================================================================
@app.route("/api/ingest", methods=["POST"])
def ingest():
    """
    Receive a JSON payload from the ESP32 and write it straight into
    the raw_telemetry table.  The background processor will pick it up
    on the next 25-second cycle.

    Expected JSON:
    {
        "device_id":   "esp32-001",
        "dust":        45.0,
        "mq135":       890.0,
        "mq7":         580.0,
        "temperature": 28.5,
        "humidity":    65.0,
        "pressure":    1013.25,
        "gas":         50000.0,
        "latitude":    12.9716,
        "longitude":   77.5946
    }
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "Missing device_id"}), 400

    try:
        # Auto-register the device if we haven't seen it before
        device = db.get_or_create_device(device_id)
        if not device:
            return jsonify({"error": "Device registration failed"}), 500

        # Store the raw reading
        row = db.insert_raw_telemetry(device_id, data)
        if not row:
            return jsonify({"error": "Insert failed"}), 500

        log.info(f"Ingested raw telemetry from {device_id}  (id={row.get('id')})")

        return jsonify({
            "ok": True,
            "telemetry_id": row.get("id"),
            "ts": datetime.now(timezone.utc).isoformat(),
        }), 201

    except Exception as exc:
        log.error(f"Ingest error: {exc}")
        return jsonify({"error": str(exc)}), 500


# =============================================================================
#  GET /api/health
# =============================================================================
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "GreenRoute Mesh v2",
        "ts": datetime.now(timezone.utc).isoformat(),
    })


# =============================================================================
#  PROCESSING WORKER  (called by background thread + manual endpoint)
# =============================================================================

def process_pending() -> int:
    """
    Fetch all raw_telemetry rows where processed=false, run the processor,
    write to processed_data, and mark each row as processed.
    Returns the number of rows processed.
    """
    count = 0
    rows = db.get_unprocessed_telemetry(limit=200)

    for raw in rows:
        try:
            device = raw.get("devices") or db.get_device(raw["device_id"])
            if not device:
                log.warning(f"Unknown device {raw['device_id']} — skipping")
                continue

            enriched = processor.process(raw, device)
            db.insert_processed_data(enriched)
            db.mark_telemetry_processed(raw["id"])
            count += 1
        except Exception as exc:
            log.error(f"Processing row {raw.get('id')} failed: {exc}")

    return count


# =============================================================================
#  POST /api/process  — manual trigger
# =============================================================================
@app.route("/api/process", methods=["POST"])
def trigger_processing():
    n = process_pending()
    return jsonify({
        "ok": True,
        "processed": n,
        "ts": datetime.now(timezone.utc).isoformat(),
    })


# =============================================================================
#  GET /api/readings  — latest processed data
# =============================================================================
@app.route("/api/readings", methods=["GET"])
def get_readings():
    device_id = request.args.get("device_id")
    limit = request.args.get("limit", 100, type=int)
    data = db.get_latest_processed(device_id=device_id, limit=limit)
    return jsonify({"ok": True, "data": data, "count": len(data)})


# =============================================================================
#  GET /api/stats
# =============================================================================
@app.route("/api/stats", methods=["GET"])
def stats():
    return jsonify({"ok": True, **db.get_statistics()})


# =============================================================================
#  BACKGROUND WORKER  (every PROCESS_INTERVAL seconds)
# =============================================================================

PROCESS_INTERVAL = int(os.environ.get("PROCESS_INTERVAL", 25))


def _background_loop():
    """Runs forever in a daemon thread — processes pending rows on a timer."""
    log.info(f"Background worker started  (interval={PROCESS_INTERVAL}s)")
    while True:
        try:
            n = process_pending()
            if n:
                log.info(f"Background worker processed {n} row(s)")
        except Exception as exc:
            log.error(f"Background worker error: {exc}")
        time.sleep(PROCESS_INTERVAL)


# =============================================================================
#  MAIN
# =============================================================================
if __name__ == "__main__":
    # Start background processing thread
    t = threading.Thread(target=_background_loop, daemon=True)
    t.start()

    port = int(os.environ.get("PORT", 5001))
    log.info(f"GreenRoute Mesh v2 starting on :{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
