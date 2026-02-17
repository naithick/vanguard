"""
GreenRoute Mesh v2 — API Server

POST /api/ingest    — ESP32 sends raw sensor JSON → stored + processed in real-time
POST /api/process   — manually trigger processing of any missed rows
GET  /api/readings  — latest processed readings
GET  /api/zones     — interpolated air-quality zone GeoJSON
GET  /api/stats     — quick summary counts
GET  /api/health    — health-check

ALERTS:
GET  /api/alerts            — list alerts (filters: active, severity, type)
GET  /api/alerts/<id>       — single alert
POST /api/alerts            — create alert (manual)
PUT  /api/alerts/<id>/resolve — resolve an alert

REPORTS (anonymous, no login):
GET  /api/reports           — list reports (filters: status, category)
GET  /api/reports/<id>      — single report
POST /api/reports           — create report
PUT  /api/reports/<id>/status — update status
POST /api/reports/<id>/upvote — upvote a report

Real-time: each ingest request immediately processes the row inline.
Background worker (safety net) runs every 30 s to catch any rows that
slipped through (errors, race conditions, CSV bulk loads).
Auto-alerts: when AQI exceeds thresholds during processing.
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
                # Auto-alert if AQI is high
                try:
                    check_and_create_alert(enriched, device)
                except Exception as alert_exc:
                    log.warning(f"Auto-alert check failed: {alert_exc}")
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
    Fetch all raw_telemetry rows where processed=false, run the full
    data-cleaning pipeline (bounds check, IQR outlier clipping, sensor
    calibration, AQI, heat index, toxic gas index, respiratory risk,
    GPS fallback, movement tracking), then batch-write to processed_data.

    Batched DB ops: fetch 1000 → process in-memory → batch insert → batch mark.
    Returns {"processed": N, "dropped": M}.
    """
    total_processed = 0
    total_dropped = 0

    while True:
        rows = db.get_unprocessed_telemetry(limit=1000)
        if not rows:
            break

        enriched_batch = []
        mark_ids = []  # all IDs to mark as processed (passed + dropped)

        for raw in rows:
            try:
                device = raw.get("devices") or db.get_device(raw["device_id"])
                if not device:
                    log.warning(f"Unknown device {raw['device_id']} — skipping")
                    continue

                result = processor.process(raw, device)

                if result is None:
                    # Failed validation (bounds/null/outlier) — still mark done
                    mark_ids.append(raw["id"])
                    total_dropped += 1
                    continue

                enriched_batch.append(result)
                mark_ids.append(raw["id"])
            except Exception as exc:
                exc_msg = str(exc)
                if "23505" in exc_msg or "duplicate key" in exc_msg.lower():
                    mark_ids.append(raw["id"])
                    total_processed += 1
                else:
                    log.error(f"Processing row {raw.get('id')} failed: {exc}")

        # Auto-alert check for batch processing
        for row in enriched_batch:
            try:
                device_info = db.get_device(row.get("device_id"))
                if device_info:
                    check_and_create_alert(row, device_info)
            except Exception as alert_exc:
                log.warning(f"Batch auto-alert check failed: {alert_exc}")

        # Batch DB writes
        if enriched_batch:
            try:
                db.batch_insert_processed(enriched_batch)
                total_processed += len(enriched_batch)
            except Exception as exc:
                log.error(f"Batch insert failed: {exc}")
                # Fall back to per-row insert to salvage what we can
                for row in enriched_batch:
                    try:
                        db.insert_processed_data(row)
                        total_processed += 1
                    except Exception:
                        total_dropped += 1

        if mark_ids:
            db.batch_mark_processed(mark_ids)

        log.info(f"Batch done: {len(enriched_batch)} processed, "
                 f"{total_dropped} dropped so far ({len(rows)} fetched)")

        if len(rows) < 1000:
            break  # no more rows

    return {"processed": total_processed, "dropped": total_dropped}


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
#  DASHBOARD ENDPOINTS
# =============================================================================

@app.route("/api/devices", methods=["GET"])
def get_devices():
    """
    Get all registered devices with their latest reading.
    Returns: [{device_info, latest_reading}, ...]
    """
    try:
        devices = db.get_all_devices()
        enriched = []
        
        for device in devices:
            device_id = device.get("device_id")
            # Fetch latest reading for this device
            latest = db.get_latest_processed(device_id=device_id, limit=1)
            enriched.append({
                "device": device,
                "latest_reading": latest[0] if latest else None,
            })
        
        return jsonify({"ok": True, "devices": enriched, "count": len(enriched)})
    except Exception as exc:
        log.error(f"Get devices error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/devices/<device_id>", methods=["GET"])
def get_device_info(device_id):
    """
    Get detailed info for a specific device.
    """
    try:
        device = db.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # Get some recent readings
        limit = request.args.get("limit", 20, type=int)
        readings = db.get_latest_processed(device_id=device_id, limit=limit)
        
        return jsonify({
            "ok": True,
            "device": device,
            "recent_readings": readings,
            "readings_count": len(readings),
        })
    except Exception as exc:
        log.error(f"Get device info error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/devices/<device_id>/latest", methods=["GET"])
def get_device_latest(device_id):
    """
    Get the most recent reading for a specific device.
    """
    try:
        device = db.get_device(device_id)
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        latest = db.get_latest_processed(device_id=device_id, limit=1)
        
        return jsonify({
            "ok": True,
            "device_id": device_id,
            "latest_reading": latest[0] if latest else None,
        })
    except Exception as exc:
        log.error(f"Get device latest error: {exc}")
        return jsonify({"error": str(exc)}), 500


# =============================================================================
#  GET /api/stats
# =============================================================================
@app.route("/api/stats", methods=["GET"])
def stats():
    return jsonify({"ok": True, **db.get_statistics()})


# =============================================================================
#  ALERTS
# =============================================================================

# AQI thresholds for auto-alerts
# alert_type must be one of: aqi, pm25, co (DB check constraint)
# severity must be one of: critical, warning, info, danger
AQI_THRESHOLDS = [
    (301, "critical",  "Hazardous air quality"),
    (201, "danger",    "Very unhealthy air quality"),
    (151, "warning",   "Unhealthy air quality"),
    (101, "info",      "Unhealthy for sensitive groups"),
]

VALID_ALERT_TYPES = {"aqi", "pm25", "co"}
VALID_ALERT_SEVERITIES = {"critical", "warning", "info", "danger"}


def check_and_create_alert(enriched: dict, device: dict):
    """Auto-create an alert if AQI exceeds thresholds. No duplicates for same device."""
    aqi = enriched.get("aqi_value")
    if not aqi:
        return

    for threshold, severity, msg in AQI_THRESHOLDS:
        if aqi >= threshold:
            # Don't create duplicate active AQI alerts for same device
            existing = db.get_active_alert_for_device(
                device.get("device_id"), "aqi"
            )
            if existing:
                return  # already have an active alert

            db.create_alert({
                "device_id":  device.get("device_id"),
                "alert_type": "aqi",
                "severity":   severity,
                "title":      f"AQI {int(aqi)} - {msg}",
                "message":    f"Device {device.get('name', device.get('device_id'))} "
                              f"recorded AQI {int(aqi)}. {msg}.",
                "latitude":   enriched.get("latitude"),
                "longitude":  enriched.get("longitude"),
            })
            log.warning(f"AUTO-ALERT: aqi for {device.get('device_id')} (AQI={int(aqi)})")
            return  # only create for the highest matching threshold


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    """
    List alerts.
    Query params: active (bool), severity, alert_type, limit (default 50)
    """
    try:
        active_only = request.args.get("active", "").lower() in ("true", "1", "yes")
        severity = request.args.get("severity")
        alert_type = request.args.get("alert_type")
        limit = request.args.get("limit", 50, type=int)

        alerts = db.get_alerts(
            active_only=active_only,
            severity=severity,
            alert_type=alert_type,
            limit=limit,
        )
        return jsonify({"ok": True, "alerts": alerts, "count": len(alerts)})
    except Exception as exc:
        log.error(f"Get alerts error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/alerts/<alert_id>", methods=["GET"])
def get_alert(alert_id):
    """Get a single alert by ID."""
    try:
        alert = db.get_alert(alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
        return jsonify({"ok": True, "alert": alert})
    except Exception as exc:
        log.error(f"Get alert error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/alerts", methods=["POST"])
def create_alert():
    """
    Manually create an alert.
    JSON body: {title, message, severity, alert_type, device_id, latitude, longitude}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON payload"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    # Validate alert_type and severity against DB constraints
    at = data.get("alert_type", "aqi")
    if at not in VALID_ALERT_TYPES:
        return jsonify({"error": f"Invalid alert_type. Valid: {sorted(VALID_ALERT_TYPES)}"}), 400
    data["alert_type"] = at

    sev = data.get("severity", "info")
    if sev not in VALID_ALERT_SEVERITIES:
        return jsonify({"error": f"Invalid severity. Valid: {sorted(VALID_ALERT_SEVERITIES)}"}), 400
    data["severity"] = sev

    try:
        alert = db.create_alert(data)
        return jsonify({"ok": True, "alert": alert}), 201
    except Exception as exc:
        log.error(f"Create alert error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/alerts/<alert_id>/resolve", methods=["PUT"])
def resolve_alert(alert_id):
    """Mark an alert as resolved."""
    try:
        alert = db.resolve_alert(alert_id)
        if not alert:
            return jsonify({"error": "Alert not found"}), 404
        return jsonify({"ok": True, "alert": alert})
    except Exception as exc:
        log.error(f"Resolve alert error: {exc}")
        return jsonify({"error": str(exc)}), 500


# =============================================================================
#  USER REPORTS  (anonymous, no login required)
# =============================================================================

VALID_CATEGORIES = {"smoke", "dust", "smell", "traffic", "industrial", "construction", "burning", "general", "other"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_STATUSES   = {"open", "investigating", "resolved"}


@app.route("/api/reports", methods=["GET"])
def get_reports():
    """
    List user reports.
    Query params: status, category, limit (default 50)
    """
    try:
        status = request.args.get("status")
        category = request.args.get("category")
        limit = request.args.get("limit", 50, type=int)

        reports = db.get_reports(status=status, category=category, limit=limit)
        return jsonify({"ok": True, "reports": reports, "count": len(reports)})
    except Exception as exc:
        log.error(f"Get reports error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reports/<report_id>", methods=["GET"])
def get_report(report_id):
    """Get a single report by ID."""
    try:
        report = db.get_report(report_id)
        if not report:
            return jsonify({"error": "Report not found"}), 404
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        log.error(f"Get report error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reports", methods=["POST"])
def create_report():
    """
    Create an anonymous user report.
    JSON body: {title (required), description, category, severity, latitude, longitude, reporter_name}
    Categories: smoke, dust, smell, traffic, industrial, construction, burning, general, other
    Severities: low, medium, high, critical
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON payload"}), 400
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    # Validate category & severity
    cat = data.get("category", "general").lower()
    if cat not in VALID_CATEGORIES:
        return jsonify({"error": f"Invalid category. Valid: {sorted(VALID_CATEGORIES)}"}), 400
    data["category"] = cat

    sev = data.get("severity", "medium").lower()
    if sev not in VALID_SEVERITIES:
        return jsonify({"error": f"Invalid severity. Valid: {sorted(VALID_SEVERITIES)}"}), 400
    data["severity"] = sev

    try:
        report = db.create_report(data)
        return jsonify({"ok": True, "report": report}), 201
    except Exception as exc:
        log.error(f"Create report error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reports/<report_id>/status", methods=["PUT"])
def update_report_status(report_id):
    """
    Update report status.
    JSON body: {status: "open" | "investigating" | "resolved"}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("status"):
        return jsonify({"error": "status is required"}), 400

    status = data["status"].lower()
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Valid: {sorted(VALID_STATUSES)}"}), 400

    try:
        report = db.update_report_status(report_id, status)
        if not report:
            return jsonify({"error": "Report not found"}), 404
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        log.error(f"Update report status error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/reports/<report_id>/upvote", methods=["POST"])
def upvote_report(report_id):
    """Upvote a report (anonymous, no login)."""
    try:
        report = db.upvote_report(report_id)
        if not report:
            return jsonify({"error": "Report not found"}), 404
        return jsonify({"ok": True, "report": report})
    except Exception as exc:
        log.error(f"Upvote report error: {exc}")
        return jsonify({"error": str(exc)}), 500


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
