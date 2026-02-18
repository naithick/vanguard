import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import type { DeviceWithReading, Reading } from '../api/client';

// Fix for default marker icon in React Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

interface AirQualityMapProps {
  devices?: DeviceWithReading[];
  readings?: Reading[];
  selectedDeviceID?: string | null;
}

// Component to handle map view changes
const ChangeView = ({ center, zoom }: { center: [number, number], zoom: number }) => {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom, {
      duration: 2
    });
  }, [center, zoom, map]);
  return null;
};

const AirQualityMap = ({ devices = [], readings = [], selectedDeviceID }: AirQualityMapProps) => {
  // Logic to determine map center
  // If a device is selected, center on it. Otherwise center on the average of all active devices.
  const activeNodes = useMemo(() => {
    return devices.filter(d => d.latest_reading !== null).map(d => ({
      id: d.device.device_id,
      name: d.device.name,
      position: [d.latest_reading!.latitude, d.latest_reading!.longitude] as [number, number],
      aqi: d.latest_reading!.aqi_value,
      status: d.latest_reading!.aqi_category,
      timestamp: d.latest_reading!.recorded_at
    }));
  }, [devices]);

  const center = useMemo(() => {
    if (selectedDeviceID) {
      const selected = activeNodes.find(n => n.id === selectedDeviceID);
      if (selected) return selected.position;
    }
    if (activeNodes.length > 0) {
      const avgLat = activeNodes.reduce((acc, n) => acc + n.position[0], 0) / activeNodes.length;
      const avgLon = activeNodes.reduce((acc, n) => acc + n.position[1], 0) / activeNodes.length;
      return [avgLat, avgLon] as [number, number];
    }
    return [12.9229, 80.1275] as [number, number]; // Tambaram fallback
  }, [activeNodes, selectedDeviceID]);

  const zoom = selectedDeviceID ? 15 : 13;

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'good': return 'var(--status-good)';
      case 'moderate': return 'var(--status-warning)';
      case 'unhealthy for sensitive groups': return 'var(--status-critical)';
      case 'unhealthy': return '#1e40af';
      case 'very unhealthy': return '#1e3a8a';
      case 'hazardous': return '#172554';
      default: return 'var(--status-good)';
    }
  };

  // Trajectory logic: group readings by device and show polylines
  const trajectories = useMemo(() => {
    const groups: Record<string, [number, number][]> = {};
    readings.forEach(r => {
      if (!groups[r.device_id]) groups[r.device_id] = [];
      groups[r.device_id].push([r.latitude, r.longitude]);
    });
    return Object.entries(groups).map(([id, positions]) => ({
      id,
      positions: positions.slice(0, 50) as [number, number][] // Show last 50 points
    }));
  }, [readings]);

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm h-full relative overflow-hidden flex flex-col">
      {/* Map Header */}
      <div className="absolute top-4 left-4 z-[400] bg-white/90 backdrop-blur-sm rounded-xl p-3 shadow-lg pointer-events-none border border-gray-100">
        <div className="text-sm font-bold text-gray-800">Mesh Live Map</div>
        <div className="text-[10px] text-gray-500 uppercase tracking-tighter">
          {activeNodes.length} Nodes Active • {new Date().toLocaleTimeString()}
        </div>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 z-[400] bg-white/90 backdrop-blur-sm rounded-xl p-3 shadow-lg pointer-events-none border border-gray-100">
        <div className="text-[10px] font-bold text-gray-400 mb-2 uppercase tracking-wide">AQI Status</div>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 bg-status-good rounded-full"></div>
            <span className="text-[10px] text-gray-600 font-medium">Good</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 bg-status-warning rounded-full"></div>
            <span className="text-[10px] text-gray-600 font-medium">Moderate</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 bg-status-critical rounded-full"></div>
            <span className="text-[10px] text-gray-600 font-medium">Unhealthy</span>
          </div>
        </div>
      </div>

      <div className="flex-1 rounded-xl overflow-hidden z-0">
        <MapContainer
          center={center}
          zoom={zoom}
          scrollWheelZoom={true}
          className="h-full w-full"
        >
          <ChangeView center={center} zoom={zoom} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {activeNodes.map((node) => (
            <Marker key={node.id} position={node.position}>
              <Popup className="custom-popup">
                <div className="p-1 min-w-[140px]">
                  <div className="font-bold text-gray-800 border-b pb-1 mb-1 text-xs">Node: {node.name}</div>
                  <div className="flex justify-between items-center text-[10px] mb-1">
                    <span className="text-gray-400">AQI:</span>
                    <span className="font-bold">{Math.round(node.aqi)}</span>
                  </div>
                  <div className="flex justify-between items-center text-[11px]">
                    <span className="text-gray-500 font-medium capitalize" style={{ color: getStatusColor(node.status) }}>
                      {node.status}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-400 mt-2 italic">
                    Updated: {new Date(node.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

          {/* Device Trajectories */}
          {trajectories.map((trail) => (
            <Polyline
              key={trail.id}
              positions={trail.positions}
              pathOptions={{
                color: trail.id === selectedDeviceID ? '#06b6d4' : '#94a3b8',
                weight: 3,
                opacity: 0.6,
                dashArray: '5, 10'
              }}
            />
          ))}
        </MapContainer>
      </div>
    </div>
  );
};

export default AirQualityMap;
