"""
GreenRoute Mesh - Supabase Client
Database operations for air quality monitoring
"""

from supabase import create_client, Client
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

from config import supabase_config

log = logging.getLogger('greenroute.db')

class SupabaseClient:
    """Supabase database client for GreenRoute Mesh"""
    
    def __init__(self):
        # Use service_role key — bypasses RLS for full backend access
        self.client: Client = create_client(
            supabase_config.url,
            supabase_config.service_key
        )
        log.info(f"Connected to Supabase: {supabase_config.url}")
    
    # =========================================================================
    # DEVICES
    # =========================================================================
    
    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get device by device_id"""
        result = self.client.table('devices').select('*').eq('device_id', device_id).execute()
        return result.data[0] if result.data else None
    
    def register_device(self, device_id: str, name: str, 
                       static_lat: float = None, static_lon: float = None,
                       **kwargs) -> Dict:
        """Register a new ESP32 device"""
        data = {
            'device_id': device_id,
            'name': name,
            'status': 'active',
            **kwargs
        }
        if static_lat and static_lon:
            data['static_latitude'] = static_lat
            data['static_longitude'] = static_lon
        
        result = self.client.table('devices').insert(data).execute()
        log.info(f"Registered device: {device_id}")
        return result.data[0] if result.data else None
    
    def get_or_create_device(self, device_id: str, name: str = None) -> Dict:
        """Get existing device or create new one"""
        device = self.get_device(device_id)
        if device:
            return device
        return self.register_device(device_id, name or f"ESP32-{device_id[:8]}")
    
    # =========================================================================
    # RAW TELEMETRY (ESP32 Ingestion)
    # =========================================================================
    
    def insert_raw_telemetry(self, device_id: str, data: Dict) -> Dict:
        """
        Insert raw sensor reading from ESP32
        
        Expected data format:
        {
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
        row = {
            'device_id': device_id,
            'raw_dust': data.get('dust'),
            'raw_mq135': data.get('mq135'),
            'raw_mq7': data.get('mq7'),
            'temperature_c': data.get('temperature'),
            'humidity_pct': data.get('humidity'),
            'pressure_hpa': data.get('pressure'),
            'gas_resistance': data.get('gas'),
            'raw_latitude': data.get('latitude', 0),
            'raw_longitude': data.get('longitude', 0),
            'processed': False,
            'received_at': datetime.now(timezone.utc).isoformat()
        }
        
        result = self.client.table('raw_telemetry').insert(row).execute()
        log.debug(f"Inserted raw telemetry for {device_id}")
        return result.data[0] if result.data else None
    
    def get_unprocessed_telemetry(self, limit: int = 100) -> List[Dict]:
        """Get unprocessed raw telemetry rows (oldest first)"""
        result = self.client.table('raw_telemetry')\
            .select('*, devices(*)')\
            .eq('processed', False)\
            .order('received_at', desc=False)\
            .limit(limit)\
            .execute()
        return result.data
    
    def mark_telemetry_processed(self, telemetry_id: str) -> bool:
        """Mark a raw telemetry row as processed"""
        result = self.client.table('raw_telemetry')\
            .update({'processed': True})\
            .eq('id', telemetry_id)\
            .execute()
        return bool(result.data)
    
    # =========================================================================
    # PROCESSED DATA
    # =========================================================================
    
    def insert_processed_data(self, data: Dict) -> Dict:
        """Insert processed/enriched sensor data"""
        result = self.client.table('processed_data').insert(data).execute()
        log.debug(f"Inserted processed data for {data.get('device_id')}")
        return result.data[0] if result.data else None
    
    def get_latest_processed(self, device_id: str = None, limit: int = 100) -> List[Dict]:
        """Get latest processed data readings"""
        query = self.client.table('processed_data').select('*')
        if device_id:
            query = query.eq('device_id', device_id)
        result = query.order('recorded_at', desc=True).limit(limit).execute()
        return result.data
    
    def get_processed_for_map(self, hours: int = 24) -> List[Dict]:
        """Get processed data for map visualization (last N hours)"""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        result = self.client.table('processed_data')\
            .select('latitude, longitude, aqi_value, aqi_category, pm25_ugm3, co_ppm, temperature_c, humidity_pct, recorded_at')\
            .gte('recorded_at', cutoff)\
            .order('recorded_at', desc=True)\
            .execute()
        return result.data
    
    # =========================================================================
    # HOTSPOTS
    # =========================================================================
    
    def get_active_hotspots(self) -> List[Dict]:
        """Get all active pollution hotspots"""
        result = self.client.table('identified_hotspots')\
            .select('*')\
            .eq('is_active', True)\
            .execute()
        return result.data
    
    def upsert_hotspot(self, data: Dict) -> Dict:
        """Insert or update a hotspot"""
        result = self.client.table('identified_hotspots').upsert(data).execute()
        return result.data[0] if result.data else None
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        # Count devices
        devices = self.client.table('devices').select('id', count='exact').execute()
        
        # Count processed readings
        processed = self.client.table('processed_data').select('id', count='exact').execute()
        
        # Count active hotspots
        hotspots = self.client.table('identified_hotspots')\
            .select('id', count='exact').eq('is_active', True).execute()
        
        # Get latest AQI stats
        latest = self.client.table('processed_data')\
            .select('aqi_value')\
            .order('recorded_at', desc=True)\
            .limit(100)\
            .execute()
        
        aqi_values = [r['aqi_value'] for r in latest.data if r.get('aqi_value')]
        avg_aqi = sum(aqi_values) / len(aqi_values) if aqi_values else 0

        # Count active alerts
        try:
            active_alerts = self.client.table('alerts')\
                .select('id', count='exact').eq('is_active', True).execute()
            alert_count = active_alerts.count or 0
        except Exception:
            alert_count = 0
        
        return {
            'device_count': devices.count or 0,
            'total_readings': processed.count or 0,
            'active_hotspots': hotspots.count or 0,
            'active_alerts': alert_count,
            'avg_aqi_recent': round(avg_aqi, 1),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    # =========================================================================
    # ZONE DATA (for bubble clustering)
    # =========================================================================
    
    def get_all_processed_for_zones(self, hours: int = 24) -> List[Dict]:
        """Get ALL processed data fields for zone aggregation"""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        
        result = self.client.table('processed_data')\
            .select('latitude, longitude, aqi_value, aqi_category, '
                    'pm25_ugm3, co_ppm, co2_ppm, temperature_c, humidity_pct, '
                    'pressure_hpa, heat_index_c, toxic_gas_index, '
                    'respiratory_risk_label, device_id, recorded_at')\
            .gte('recorded_at', cutoff)\
            .order('recorded_at', desc=True)\
            .execute()
        return result.data
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    def insert_alert(self, data: Dict) -> Optional[Dict]:
        """Insert a new alert"""
        try:
            result = self.client.table('alerts').insert(data).execute()
            log.info(f"Alert created: {data.get('title')}")
            return result.data[0] if result.data else None
        except Exception as e:
            log.warning(f"Could not insert alert (table may not exist): {e}")
            return None
    
    def get_active_alerts(self, limit: int = 50) -> List[Dict]:
        """Get all active (unresolved) alerts"""
        try:
            result = self.client.table('alerts')\
                .select('*')\
                .eq('is_active', True)\
                .order('triggered_at', desc=True)\
                .limit(limit)\
                .execute()
            return result.data
        except Exception as e:
            log.warning(f"Could not read alerts (table may not exist): {e}")
            return []
    
    def get_alerts_history(self, limit: int = 100) -> List[Dict]:
        """Get alert history (including resolved)"""
        try:
            result = self.client.table('alerts')\
                .select('*')\
                .order('triggered_at', desc=True)\
                .limit(limit)\
                .execute()
            return result.data
        except Exception as e:
            log.warning(f"Could not read alerts: {e}")
            return []
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged"""
        try:
            result = self.client.table('alerts')\
                .update({
                    'acknowledged': True,
                    'acknowledged_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('id', alert_id)\
                .execute()
            return bool(result.data)
        except Exception:
            return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved (condition no longer true)"""
        try:
            result = self.client.table('alerts')\
                .update({
                    'is_active': False,
                    'resolved_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('id', alert_id)\
                .execute()
            return bool(result.data)
        except Exception:
            return False
    
    def resolve_alerts_by_type(self, alert_type: str, zone_id: str = None) -> int:
        """Resolve all active alerts of a given type (optionally in a zone)"""
        try:
            query = self.client.table('alerts')\
                .update({
                    'is_active': False,
                    'resolved_at': datetime.now(timezone.utc).isoformat()
                })\
                .eq('is_active', True)\
                .eq('alert_type', alert_type)
            if zone_id:
                query = query.eq('zone_id', zone_id)
            result = query.execute()
            return len(result.data) if result.data else 0
        except Exception:
            return 0


# Global client instance
db = SupabaseClient()
