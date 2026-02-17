"""
GreenRoute Mesh - API Server
Flask API for ESP32 data ingestion and dashboard

Endpoints:
  POST /api/ingest          - ESP32 raw data ingestion → raw_telemetry
  POST /api/process         - Trigger processing worker
  GET  /api/readings        - Get processed readings for map
  GET  /api/zones           - Aggregated bubble zones (clustered)
  GET  /api/hotspots        - Get active pollution hotspots
  GET  /api/stats           - Get statistics
  GET  /api/device/:id      - Get device info
  GET  /api/alerts          - Get active alerts (popup data)
  POST /api/alerts/:id/ack  - Acknowledge an alert
"""

import os
import sys
import math
import logging
from datetime import datetime, timezone
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
from collections import defaultdict

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import supabase_config, device_defaults
from supabase_client import db
from processor import processor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger('greenroute.api')

app = Flask(__name__)
CORS(app)


# =============================================================================
# ESP32 INGESTION ENDPOINT
# =============================================================================

@app.route('/api/ingest', methods=['POST'])
def ingest_telemetry():
    """
    Receive raw sensor data from ESP32
    
    Expected JSON payload:
    {
        "device_id": "esp32-001",
        "dust": 45.0,
        "mq135": 890.0,
        "mq7": 580.0,
        "temperature": 28.5,
        "humidity": 65.0,
        "pressure": 1013.25,
        "gas": 50000.0,
        "latitude": 12.9716,
        "longitude": 77.5946
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON payload'}), 400
        
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({'error': 'Missing device_id'}), 400
        
        # Ensure device exists (auto-register if new)
        device = db.get_or_create_device(device_id)
        
        if not device:
            return jsonify({'error': 'Failed to register device'}), 500
        
        # Insert raw telemetry
        result = db.insert_raw_telemetry(device_id, data)
        
        if result:
            log.info(f"Ingested telemetry from {device_id}")
            return jsonify({
                'success': True,
                'telemetry_id': result.get('id'),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 201
        else:
            return jsonify({'error': 'Failed to insert telemetry'}), 500
            
    except Exception as e:
        log.error(f"Ingestion error: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================================
# PROCESSING WORKER
# =============================================================================

def process_pending_telemetry():
    """Process all unprocessed raw telemetry rows"""
    processed_count = 0
    
    try:
        # Get unprocessed rows
        rows = db.get_unprocessed_telemetry(limit=100)
        
        for row in rows:
            try:
                # Get device for calibration factors
                device = row.get('devices') or db.get_device(row['device_id'])
                
                if not device:
                    log.warning(f"Unknown device: {row['device_id']}")
                    continue
                
                # Process the raw data
                processed = processor.process_raw_telemetry(row, device)
                
                # Insert processed data
                db.insert_processed_data(processed)
                
                # Mark as processed
                db.mark_telemetry_processed(row['id'])
                
                processed_count += 1
                
            except Exception as e:
                log.error(f"Error processing row {row.get('id')}: {e}")
                continue
        
        return processed_count
        
    except Exception as e:
        log.error(f"Processing worker error: {e}")
        return 0


@app.route('/api/process', methods=['POST'])
def trigger_processing():
    """Manually trigger processing of pending telemetry"""
    count = process_pending_telemetry()
    return jsonify({
        'success': True,
        'processed_count': count,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# Background worker thread
def background_processor():
    """Continuously process pending telemetry"""
    while True:
        try:
            count = process_pending_telemetry()
            if count > 0:
                log.info(f"Background processor: processed {count} rows")
        except Exception as e:
            log.error(f"Background processor error: {e}")
        time.sleep(5)  # Process every 5 seconds


# =============================================================================
# DASHBOARD API ENDPOINTS
# =============================================================================

@app.route('/api/readings', methods=['GET'])
def get_readings():
    """
    Get processed readings for map visualization
    
    Query params:
        hours: int (default 24) - Time window in hours
        device_id: str (optional) - Filter by device
    """
    hours = request.args.get('hours', 24, type=int)
    device_id = request.args.get('device_id')
    
    if device_id:
        data = db.get_latest_processed(device_id=device_id, limit=1000)
    else:
        data = db.get_processed_for_map(hours=hours)
    
    return jsonify({
        'success': True,
        'data': data,
        'count': len(data)
    })


@app.route('/api/readings/bubbles', methods=['GET'])
def get_bubble_data():
    """
    Get data formatted for translucent bubble visualization
    
    Returns data with:
    - lat, lng for position
    - radius based on AQI severity
    - color based on AQI category
    - opacity based on confidence
    """
    hours = request.args.get('hours', 24, type=int)
    data = db.get_processed_for_map(hours=hours)
    
    # Color mapping (green-path-ui style)
    color_map = {
        'Good': '#038a37',
        'Moderate': '#459255',
        'Unhealthy for Sensitive Groups': '#e6954e',
        'Unhealthy': '#ff6b20',
        'Very Unhealthy': '#ff4c15',
        'Hazardous': '#ff2f20'
    }
    
    bubbles = []
    for row in data:
        aqi = row.get('aqi_value') or 50
        category = row.get('aqi_category') or 'Good'
        
        # Radius based on AQI (higher = larger bubble)
        radius = 20 + (aqi / 500) * 80  # 20-100 pixels
        
        # Opacity based on recency (newer = more opaque)
        opacity = 0.3 + 0.5  # Base 0.3-0.8
        
        bubbles.append({
            'lat': row.get('latitude'),
            'lng': row.get('longitude'),
            'aqi': aqi,
            'category': category,
            'radius': radius,
            'color': color_map.get(category, '#459255'),
            'opacity': opacity,
            'pm25': row.get('pm25_ugm3'),
            'temperature': row.get('temperature_c'),
            'humidity': row.get('humidity_pct'),
            'timestamp': row.get('recorded_at')
        })
    
    return jsonify({
        'success': True,
        'bubbles': bubbles,
        'count': len(bubbles)
    })


# =============================================================================
# ZONE CLUSTERING  — aggregate discrete points into translucent bubble zones
# =============================================================================
# Uses a geohash-style grid: round lat/lng to a configurable precision so
# nearby readings merge into a single zone.  Each zone carries aggregate
# scores that the frontend can render as a translucent coloured circle.
# =============================================================================

# ----------- colour ramp (shared) -----------
AQI_COLOR_MAP = {
    'Good':                             '#038a37',
    'Moderate':                         '#f5c542',
    'Unhealthy for Sensitive Groups':   '#e6954e',
    'Unhealthy':                        '#ff6b20',
    'Very Unhealthy':                   '#ff4c15',
    'Hazardous':                        '#ff2f20',
}

SEVERITY_COLOR_MAP = {
    'info':     '#17a2b8',
    'warning':  '#ffc107',
    'danger':   '#dc3545',
    'critical': '#8b0000',
}


def _geohash_key(lat: float, lng: float, precision: int = 3) -> str:
    """
    Create a grid key by rounding lat/lng to *precision* decimal places.
    precision=3 → ~111 m cells,  precision=2 → ~1.1 km cells.
    """
    return f"{round(lat, precision)},{round(lng, precision)}"


def _safe_avg(values):
    """Average that ignores None"""
    clean = [v for v in values if v is not None]
    return round(sum(clean) / len(clean), 2) if clean else None


def _aqi_category(aqi: float) -> str:
    if aqi is None:
        return 'Good'
    if aqi <= 50:  return 'Good'
    if aqi <= 100: return 'Moderate'
    if aqi <= 150: return 'Unhealthy for Sensitive Groups'
    if aqi <= 200: return 'Unhealthy'
    if aqi <= 300: return 'Very Unhealthy'
    return 'Hazardous'


def _respiratory_worst(labels):
    """Return the worst respiratory risk label from a list"""
    order = ['Low', 'Moderate', 'High', 'Very High', 'Severe']
    worst = 0
    for l in labels:
        if l in order:
            worst = max(worst, order.index(l))
    return order[worst]


def cluster_into_zones(rows, precision: int = 3, score_type: str = 'overall'):
    """
    Cluster processed_data rows into geographic grid zones.

    score_type:
        'overall'       → composite (AQI + heat + toxic gas normalised)
        'aqi'           → AQI only
        'pm25'          → PM2.5 only
        'co'            → CO only
        'temperature'   → heat index focus
        'toxic_gas'     → toxic gas index
        'humidity'       → humidity focus
    """
    buckets = defaultdict(list)

    for row in rows:
        lat = row.get('latitude')
        lng = row.get('longitude')
        if lat is None or lng is None:
            continue
        key = _geohash_key(lat, lng, precision)
        buckets[key].append(row)

    zones = []
    for key, points in buckets.items():
        n = len(points)

        # Centre of the zone (average of all points in the cell)
        center_lat = _safe_avg([p['latitude'] for p in points])
        center_lng = _safe_avg([p['longitude'] for p in points])

        # Aggregate metrics
        avg_aqi            = _safe_avg([p.get('aqi_value') for p in points])
        avg_pm25           = _safe_avg([p.get('pm25_ugm3') for p in points])
        avg_co             = _safe_avg([p.get('co_ppm') for p in points])
        avg_co2            = _safe_avg([p.get('co2_ppm') for p in points])
        avg_temp           = _safe_avg([p.get('temperature_c') for p in points])
        avg_humidity       = _safe_avg([p.get('humidity_pct') for p in points])
        avg_pressure       = _safe_avg([p.get('pressure_hpa') for p in points])
        avg_heat_idx       = _safe_avg([p.get('heat_index_c') for p in points])
        avg_toxic          = _safe_avg([p.get('toxic_gas_index') for p in points])
        worst_respiratory  = _respiratory_worst(
            [p.get('respiratory_risk_label', 'Low') for p in points])

        # Max values (worst-case in this zone)
        max_aqi  = max((p.get('aqi_value') or 0 for p in points), default=0)
        max_pm25 = max((p.get('pm25_ugm3') or 0 for p in points), default=0)
        max_co   = max((p.get('co_ppm') or 0 for p in points), default=0)

        # --- primary score based on score_type ---
        score_map = {
            'overall':     min(((avg_aqi or 0) / 500 * 60 +
                               (avg_toxic or 0) / 100 * 25 +
                               max(0, ((avg_heat_idx or 25) - 25) / 25) * 15), 100),
            'aqi':         min((avg_aqi or 0) / 5, 100),           # 0-500 → 0-100
            'pm25':        min((avg_pm25 or 0) / 5, 100),
            'co':          min((avg_co or 0) / 0.5, 100),
            'temperature': min(max(0, ((avg_heat_idx or 20) - 20)) / 0.3, 100),
            'toxic_gas':   avg_toxic or 0,
            'humidity':    min((avg_humidity or 0), 100),
        }
        primary_score = round(score_map.get(score_type, score_map['overall']), 1)

        # Category from average AQI
        category = _aqi_category(avg_aqi)

        # Radius: more readings = higher confidence = bigger bubble, 
        # but also scaled by severity
        base_radius = 80 + min(n, 200) * 0.5     # 80-180 metres
        severity_mult = 0.5 + (primary_score / 100) * 1.0  # 0.5-1.5×
        radius_m = round(base_radius * severity_mult, 1)

        # Opacity: higher score → more opaque, more readings → more opaque
        reading_confidence = min(n / 50, 1.0)     # saturates at 50 readings
        opacity = round(0.15 + 0.55 * (primary_score / 100)
                        + 0.15 * reading_confidence, 2)
        opacity = min(opacity, 0.85)

        color = AQI_COLOR_MAP.get(category, '#459255')

        # Timestamps
        timestamps = [p.get('recorded_at') for p in points if p.get('recorded_at')]
        latest_ts  = max(timestamps) if timestamps else None
        oldest_ts  = min(timestamps) if timestamps else None

        zones.append({
            'zone_id':    key,
            'lat':        center_lat,
            'lng':        center_lng,
            'radius_m':   radius_m,
            'color':      color,
            'opacity':    opacity,

            # Scores
            'primary_score':  primary_score,
            'score_type':     score_type,
            'aqi_category':   category,

            # Aggregated values
            'avg_aqi':            avg_aqi,
            'max_aqi':            max_aqi,
            'avg_pm25':           avg_pm25,
            'max_pm25':           max_pm25,
            'avg_co':             avg_co,
            'max_co':             max_co,
            'avg_co2':            avg_co2,
            'avg_temperature':    avg_temp,
            'avg_humidity':       avg_humidity,
            'avg_pressure':       avg_pressure,
            'avg_heat_index':     avg_heat_idx,
            'avg_toxic_gas':      avg_toxic,
            'respiratory_risk':   worst_respiratory,

            # Meta
            'reading_count': n,
            'latest':        latest_ts,
            'oldest':        oldest_ts,
        })

    # Sort zones by primary_score descending (worst first)
    zones.sort(key=lambda z: z['primary_score'], reverse=True)
    return zones


@app.route('/api/zones', methods=['GET'])
def get_zones():
    """
    Aggregated translucent bubble zones.

    Query params:
        hours:     int   (default 9999) — time window
        precision: int   (default 3)    — grid precision (2=~1km, 3=~111m, 4=~11m)
        score:     str   (default 'overall') — 'overall'|'aqi'|'pm25'|'co'|'temperature'|'toxic_gas'|'humidity'
    """
    hours     = request.args.get('hours', 9999, type=int)
    precision = request.args.get('precision', 3, type=int)
    score     = request.args.get('score', 'overall')

    precision = max(1, min(precision, 5))   # clamp 1-5
    valid_scores = ('overall', 'aqi', 'pm25', 'co', 'temperature', 'toxic_gas', 'humidity')
    if score not in valid_scores:
        score = 'overall'

    data = db.get_all_processed_for_zones(hours=hours)
    zones = cluster_into_zones(data, precision=precision, score_type=score)

    return jsonify({
        'success': True,
        'zones': zones,
        'count': len(zones),
        'meta': {
            'hours': hours,
            'precision': precision,
            'score_type': score,
            'total_readings': len(data),
        }
    })


# =============================================================================
# ALERT SYSTEM — threshold-based environmental notifications
# =============================================================================
# The background worker checks the latest zone aggregates and fires alerts
# when thresholds are exceeded.  The frontend polls /api/alerts to show
# them as popup banners.
# =============================================================================

ALERT_THRESHOLDS = {
    'aqi': [
        # (threshold, severity, title_template)
        (300, 'critical', 'HAZARDOUS Air Quality — AQI {val}'),
        (200, 'danger',   'Very Unhealthy Air — AQI {val}'),
        (150, 'warning',  'Unhealthy for Sensitive Groups — AQI {val}'),
        (100, 'info',     'Moderate Air Quality — AQI {val}'),
    ],
    'pm25': [
        (150.4, 'critical', 'Severe PM2.5 — {val} µg/m³'),
        (55.5,  'danger',   'Very High PM2.5 — {val} µg/m³'),
        (35.5,  'warning',  'High PM2.5 — {val} µg/m³'),
    ],
    'co': [
        (30.5, 'critical', 'DANGEROUS CO Level — {val} PPM'),
        (12.5, 'danger',   'High Carbon Monoxide — {val} PPM'),
        (9.5,  'warning',  'Elevated CO — {val} PPM'),
    ],
    'heat': [
        (54, 'critical', 'Extreme Heat Danger — {val}°C heat index'),
        (41, 'danger',   'Heat Warning — {val}°C heat index'),
        (33, 'warning',  'Caution: High Heat Index — {val}°C'),
    ],
    'toxic_gas': [
        (80, 'critical', 'Critical Toxic Gas Index — {val}/100'),
        (60, 'danger',   'High Toxic Gas Index — {val}/100'),
        (40, 'warning',  'Elevated Toxic Gas — {val}/100'),
    ],
}

ALERT_MESSAGES = {
    'aqi': {
        'critical': 'AQI has reached {val} in zone {zone}. Everyone should avoid outdoor activity. Close windows and use air purifiers.',
        'danger':   'AQI is {val} in zone {zone}. Sensitive groups should stay indoors. Limit prolonged outdoor exertion.',
        'warning':  'AQI is {val} in zone {zone}. People with respiratory conditions should take precautions.',
        'info':     'AQI is {val} in zone {zone}. Air quality is moderate — unusually sensitive individuals may experience symptoms.',
    },
    'pm25': {
        'critical': 'PM2.5 at {val} µg/m³ in zone {zone}. Severe respiratory risk. Stay indoors with air filtration.',
        'danger':   'PM2.5 at {val} µg/m³ in zone {zone}. Very high respiratory risk. Avoid outdoor activity.',
        'warning':  'PM2.5 at {val} µg/m³ in zone {zone}. Consider wearing N95 mask outdoors.',
    },
    'co': {
        'critical': 'CO at {val} PPM in zone {zone}. DANGER: Carbon monoxide at hazardous levels. Evacuate if indoors!',
        'danger':   'CO at {val} PPM in zone {zone}. Carbon monoxide elevated. Ensure ventilation.',
        'warning':  'CO at {val} PPM in zone {zone}. Slightly elevated carbon monoxide detected.',
    },
    'heat': {
        'critical': 'Heat index {val}°C in zone {zone}. Extreme danger of heat stroke. Stay in air conditioning.',
        'danger':   'Heat index {val}°C in zone {zone}. Heat exhaustion likely. Stay hydrated, limit exposure.',
        'warning':  'Heat index {val}°C in zone {zone}. Use caution during outdoor activities.',
    },
    'toxic_gas': {
        'critical': 'Toxic gas index {val}/100 in zone {zone}. Multiple hazardous gases detected at dangerous levels.',
        'danger':   'Toxic gas index {val}/100 in zone {zone}. Elevated gas mixture. Avoid the area.',
        'warning':  'Toxic gas index {val}/100 in zone {zone}. Slight elevation in ambient gas levels.',
    },
}

# Track which alerts are already active to avoid duplicates
_active_alert_keys = set()


def evaluate_alerts(zones):
    """
    Check each zone against thresholds and fire new alerts.
    Returns list of new alerts created.
    """
    global _active_alert_keys
    new_alerts = []

    metric_map = {
        'aqi':       'avg_aqi',
        'pm25':      'avg_pm25',
        'co':        'avg_co',
        'heat':      'avg_heat_index',
        'toxic_gas': 'avg_toxic_gas',
    }

    for zone in zones:
        zone_id = zone['zone_id']

        for alert_type, thresholds in ALERT_THRESHOLDS.items():
            field = metric_map[alert_type]
            val = zone.get(field)
            if val is None:
                continue

            for threshold, severity, title_tpl in thresholds:
                if val >= threshold:
                    # Deduplicate: one alert per type per zone
                    key = f"{alert_type}:{zone_id}:{severity}"
                    if key in _active_alert_keys:
                        break   # already fired at this or higher severity

                    _active_alert_keys.add(key)

                    title = title_tpl.format(val=round(val, 1))
                    message = ALERT_MESSAGES.get(alert_type, {}).get(
                        severity,
                        f'{alert_type} value {val} exceeded threshold {threshold} in zone {zone_id}.'
                    ).format(val=round(val, 1), zone=zone_id)

                    alert_data = {
                        'alert_type':     alert_type,
                        'severity':       severity,
                        'title':          title,
                        'message':        message,
                        'trigger_value':  round(val, 2),
                        'threshold_value': threshold,
                        'latitude':       zone.get('lat'),
                        'longitude':      zone.get('lng'),
                        'zone_id':        zone_id,
                        'is_active':      True,
                        'acknowledged':   False,
                    }

                    saved = db.insert_alert(alert_data)
                    if saved:
                        alert_data['id'] = saved.get('id')
                    new_alerts.append(alert_data)

                    break   # stop at highest severity matched

    return new_alerts


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """
    Get active alerts for popup display.

    Query params:
        active_only: bool  (default true)
        type:        str   (optional) — filter by alert_type
    """
    active_only = request.args.get('active_only', 'true').lower() == 'true'
    alert_type = request.args.get('type')

    if active_only:
        alerts = db.get_active_alerts()
    else:
        alerts = db.get_alerts_history()

    if alert_type:
        alerts = [a for a in alerts if a.get('alert_type') == alert_type]

    return jsonify({
        'success': True,
        'alerts': alerts,
        'count': len(alerts),
    })


@app.route('/api/alerts/<alert_id>/ack', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge (dismiss) an alert"""
    ok = db.acknowledge_alert(alert_id)
    if ok:
        _active_alert_keys.discard(alert_id)
        return jsonify({'success': True, 'alert_id': alert_id})
    return jsonify({'error': 'Alert not found or already acknowledged'}), 404


@app.route('/api/alerts/evaluate', methods=['POST'])
def manual_evaluate_alerts():
    """Manually trigger alert evaluation against current zones"""
    hours = request.args.get('hours', 9999, type=int)
    data = db.get_all_processed_for_zones(hours=hours)
    zones = cluster_into_zones(data)
    new_alerts = evaluate_alerts(zones)
    return jsonify({
        'success': True,
        'new_alerts': new_alerts,
        'count': len(new_alerts),
    })


@app.route('/api/hotspots', methods=['GET'])
def get_hotspots():
    """Get active pollution hotspots"""
    data = db.get_active_hotspots()
    return jsonify({
        'success': True,
        'hotspots': data,
        'count': len(data)
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    stats = db.get_statistics()
    return jsonify({
        'success': True,
        **stats
    })


@app.route('/api/device/<device_id>', methods=['GET'])
def get_device(device_id):
    """Get device info"""
    device = db.get_device(device_id)
    if device:
        return jsonify({'success': True, 'device': device})
    return jsonify({'error': 'Device not found'}), 404


@app.route('/api/device', methods=['POST'])
def register_device():
    """Register a new device"""
    data = request.get_json()
    device_id = data.get('device_id')
    name = data.get('name', f'ESP32-{device_id[:8]}')
    
    device = db.register_device(
        device_id=device_id,
        name=name,
        static_lat=data.get('latitude'),
        static_lon=data.get('longitude'),
        description=data.get('description')
    )
    
    return jsonify({'success': True, 'device': device}), 201


@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        'status': 'ok',
        'service': 'GreenRoute Mesh API',
        'supabase': supabase_config.url,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# =============================================================================
# MAIN
# =============================================================================

# Background worker thread
def background_processor():
    """Continuously process pending telemetry and evaluate alerts"""
    alert_cycle = 0
    while True:
        try:
            count = process_pending_telemetry()
            if count > 0:
                log.info(f"Background processor: processed {count} rows")

            # Evaluate alerts every 6th cycle (~30s)
            alert_cycle += 1
            if alert_cycle >= 6:
                alert_cycle = 0
                try:
                    data = db.get_all_processed_for_zones(hours=1)
                    if data:
                        zones = cluster_into_zones(data)
                        new = evaluate_alerts(zones)
                        if new:
                            log.info(f"Alert evaluator: {len(new)} new alert(s)")
                except Exception as e:
                    log.error(f"Alert evaluator error: {e}")

        except Exception as e:
            log.error(f"Background processor error: {e}")
        time.sleep(5)  # Process every 5 seconds


if __name__ == '__main__':
    # Start background processor
    worker_thread = threading.Thread(target=background_processor, daemon=True)
    worker_thread.start()
    log.info("Started background processing worker")
    
    # Run Flask
    port = int(os.environ.get('PORT', 5001))
    log.info(f"Starting GreenRoute Mesh API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
