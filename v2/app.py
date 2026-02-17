"""
GreenRoute Mesh v2 — API Server  (Step 1: Ingestion only)

POST /api/ingest   — ESP32 sends raw sensor JSON → stored in raw_telemetry
GET  /api/health   — quick health-check
"""

import os
import sys
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

# Allow imports from the same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_client import db

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
#  MAIN
# =============================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    log.info(f"GreenRoute Mesh v2 starting on :{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
