"""
GreenRoute Mesh v2 — API Server

POST /api/ingest    — ESP32 sends raw sensor JSON → stored + processed in real-time
POST /api/process   — manually trigger processing of any missed rows
GET  /api/readings  — latest processed readings
GET  /api/zones     — interpolated air-quality zone GeoJSON
GET  /api/stats     — quick summary counts
GET  /api/health    — health-check

Real-time: each ingest request immediately processes the row inline.
Background worker (safety net) runs every 30 s to catch any rows that
slipped through (errors, race conditions, CSV bulk loads).
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
from zones import zone_builder

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-22s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("greenroute.api")

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=".", static_url_path="/static")
CORS(app)


# =============================================================================
#  GET /  — dev map viewer
# =============================================================================
@app.route("/")
def index():
    return app.send_static_file("map.html")


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

        telemetry_id = row.get("id")
        log.info(f"Ingested raw telemetry from {device_id}  (id={telemetry_id})")

        # ── REAL-TIME PROCESSING ──────────────────────────────────────
        # Process immediately — no waiting for background worker.
        processed_row = None
        process_status = "skipped"
        try:
            # Attach device info so processor doesn't need a second query
            row["devices"] = device
            enriched = processor.process(row, device)

            if enriched is None:
                db.mark_telemetry_processed(telemetry_id)
                process_status = "dropped"  # failed validation
                log.info(f"Row {telemetry_id} dropped by validator")
            else:
                processed_row = db.insert_processed_data(enriched)
                db.mark_telemetry_processed(telemetry_id)
                process_status = "processed"
                log.info(
                    f"Real-time processed {device_id}: "
                    f"PM2.5={enriched.get('pm25_ugm3')}, "
                    f"AQI={enriched.get('aqi_value')}"
                )
        except Exception as proc_exc:
            # Processing failed — background worker will retry
            process_status = "deferred"
            log.warning(f"Real-time processing failed, deferred: {proc_exc}")

        return jsonify({
            "ok": True,
            "telemetry_id": telemetry_id,
            "process_status": process_status,
            "processed": processed_row,
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

def process_pending() -> dict:
    """
    Fetch all raw_telemetry rows where processed=false, run the processor,
    write to processed_data, and mark each row as processed.
    Returns {"processed": N, "dropped": M}.
    """
    processed = 0
    dropped = 0
    rows = db.get_unprocessed_telemetry(limit=200)

    for raw in rows:
        try:
            device = raw.get("devices") or db.get_device(raw["device_id"])
            if not device:
                log.warning(f"Unknown device {raw['device_id']} — skipping")
                continue

            enriched = processor.process(raw, device)

            if enriched is None:
                # Row failed validation — mark as processed so we don't retry
                db.mark_telemetry_processed(raw["id"])
                dropped += 1
                continue

            db.insert_processed_data(enriched)
            db.mark_telemetry_processed(raw["id"])
            processed += 1
        except Exception as exc:
            exc_msg = str(exc)
            # Duplicate key = already processed (real-time beat us to it)
            if "23505" in exc_msg or "duplicate key" in exc_msg.lower():
                log.debug(f"Row {raw.get('id')} already processed — marking done")
                db.mark_telemetry_processed(raw["id"])
                processed += 1
            else:
                log.error(f"Processing row {raw.get('id')} failed: {exc}")

    return {"processed": processed, "dropped": dropped}


# =============================================================================
#  POST /api/process  — manual trigger
# =============================================================================
@app.route("/api/process", methods=["POST"])
def trigger_processing():
    result = process_pending()
    return jsonify({
        "ok": True,
        **result,
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
#  GET /api/zones  — interpolated air-quality zones (GeoJSON)
# =============================================================================
@app.route("/api/zones", methods=["GET"])
def zones():
    """
    Return a GeoJSON FeatureCollection of interpolated air-quality zones.

    Query params:
      device_id  — filter by device  (optional)
      limit      — max readings to use (default 200)
      field      — which metric to interpolate (default: aqi_value)
      mode       — "heatmap" (grid cells), "contours" (AQI bands),
                   "points" (raw markers), or "all" (default: heatmap)
      resolution — grid size NxN (default 30, max 80)
      radius     — influence radius in metres (default 500)
    """
    device_id  = request.args.get("device_id")
    limit      = request.args.get("limit", 200, type=int)
    field      = request.args.get("field", "aqi_value")
    mode       = request.args.get("mode", "heatmap")
    resolution = request.args.get("resolution", 30, type=int)
    radius     = request.args.get("radius", 500, type=float)

    resolution = max(5, min(resolution, 80))

    # Fetch latest processed data
    data = db.get_latest_processed(device_id=device_id, limit=limit)
    if not data:
        return jsonify({"ok": True, "geojson": zone_builder._empty_fc()})

    # Temporarily override builder settings
    zone_builder.grid_resolution = resolution
    zone_builder.influence_radius_m = radius

    if mode == "contours":
        geojson = zone_builder.build_contour_zones(data, field=field)
    elif mode == "points":
        geojson = zone_builder.build_point_layer(data, field=field)
    elif mode == "all":
        geojson = {
            "heatmap":  zone_builder.build_heatmap(data, field=field),
            "contours": zone_builder.build_contour_zones(data, field=field),
            "points":   zone_builder.build_point_layer(data, field=field),
        }
        return jsonify({"ok": True, **geojson})
    else:  # default: heatmap
        geojson = zone_builder.build_heatmap(data, field=field)

    return jsonify({"ok": True, "geojson": geojson})


# =============================================================================
#  BACKGROUND WORKER  (every PROCESS_INTERVAL seconds)
# =============================================================================

PROCESS_INTERVAL = int(os.environ.get("PROCESS_INTERVAL", 30))


def _background_loop():
    """Runs forever in a daemon thread — processes pending rows on a timer."""
    log.info(f"Background worker started  (interval={PROCESS_INTERVAL}s)")
    while True:
        try:
            result = process_pending()
            if result["processed"] or result["dropped"]:
                log.info(
                    f"Background worker: {result['processed']} processed, "
                    f"{result['dropped']} dropped"
                )
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
