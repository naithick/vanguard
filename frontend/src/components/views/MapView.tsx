import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, ImageOverlay, GeoJSON, CircleMarker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix Leaflet default icon issue
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// ── Config ───────────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:5001'; // Should match backend
const DEFAULT_CENTER: [number, number] = [12.8234, 80.0441];
const DEFAULT_ZOOM = 13;

interface FieldScale {
    min: number;
    max: number;
    label: string;
    unit: string;
    useAqiColors?: boolean;
    colors?: string[];
}

const FIELD_SCALES: Record<string, FieldScale> = {
    aqi_value: { min: 0, max: 500, label: 'AQI', unit: '', useAqiColors: true },
    pm25_ugm3: { min: 0, max: 150, label: 'PM2.5', unit: 'µg/m³', colors: ['#00e400', '#ffff00', '#ff7e00', '#ff0000'] },
    temperature_c: { min: 20, max: 45, label: 'Temperature', unit: '°C', colors: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#fee090', '#fdae61', '#f46d43', '#d73027'] },
    humidity_pct: { min: 30, max: 100, label: 'Humidity', unit: '%', colors: ['#fff5eb', '#fdd49e', '#fdbb84', '#fc8d59', '#e34a33', '#b30000'] },
    co2_ppm: { min: 400, max: 2000, label: 'CO₂', unit: 'PPM', colors: ['#00e400', '#ffff00', '#ff7e00', '#ff0000'] },
    co_ppm: { min: 0, max: 50, label: 'CO', unit: 'PPM', colors: ['#00e400', '#ffff00', '#ff7e00', '#ff0000'] },
    heat_index_c: { min: 25, max: 50, label: 'Heat Index', unit: '°C', colors: ['#313695', '#74add1', '#fee090', '#fdae61', '#f46d43', '#d73027'] },
    toxic_gas_index: { min: 0, max: 100, label: 'Toxic Gas Idx', unit: '', colors: ['#00e400', '#ffff00', '#ff7e00', '#ff0000'] },
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function lerpColor(a: string, b: string, t: number) {
    const ah = parseInt(a.slice(1), 16), bh = parseInt(b.slice(1), 16);
    const ar = (ah >> 16) & 0xff, ag = (ah >> 8) & 0xff, ab = ah & 0xff;
    const br = (bh >> 16) & 0xff, bg = (bh >> 8) & 0xff, bb = bh & 0xff;
    const rr = Math.round(ar + (br - ar) * t);
    const rg = Math.round(ag + (bg - ag) * t);
    const rb = Math.round(ab + (bb - ab) * t);
    return `#${((rr << 16) | (rg << 8) | rb).toString(16).padStart(6, '0')}`;
}

function aqiColor(aqi: number) {
    if (aqi <= 50) return '#00e400';
    if (aqi <= 100) return '#ffff00';
    if (aqi <= 150) return '#ff7e00';
    if (aqi <= 200) return '#ff0000';
    if (aqi <= 300) return '#8f3f97';
    return '#7e0023';
}

function valueToColor(value: number, field: string) {
    const scale = FIELD_SCALES[field];
    if (!scale) return '#888';
    if (scale.useAqiColors) return aqiColor(value);

    const colors = scale.colors || [];
    const t = Math.max(0, Math.min(1, (value - scale.min) / (scale.max - scale.min)));
    const idx = t * (colors.length - 1);
    const lo = Math.floor(idx);
    const hi = Math.min(lo + 1, colors.length - 1);
    const frac = idx - lo;
    return lerpColor(colors[lo], colors[hi], frac);
}

// ── Components ──────────────────────────────────────────────────────────────────

const Legend = ({ field }: { field: string }) => {
    const scale = FIELD_SCALES[field];
    if (!scale) return null;

    return (
        <div className="bg-white p-4 rounded-xl shadow-lg border border-gray-100 text-xs absolute bottom-8 right-8 z-[1000]">
            <h3 className="font-bold text-gray-700 mb-2">{scale.label} Scale</h3>
            {scale.useAqiColors ? (
                <div className="space-y-1">
                    <div className="flex items-center gap-2"><div className="w-4 h-3 rounded bg-[#00e400]"></div> Good (0–50)</div>
                    <div className="flex items-center gap-2"><div className="w-4 h-3 rounded bg-[#ffff00]"></div> Moderate (51–100)</div>
                    <div className="flex items-center gap-2"><div className="w-4 h-3 rounded bg-[#ff7e00]"></div> Sensitive (101–150)</div>
                    <div className="flex items-center gap-2"><div className="w-4 h-3 rounded bg-[#ff0000]"></div> Unhealthy (151–200)</div>
                    <div className="flex items-center gap-2"><div className="w-4 h-3 rounded bg-[#8f3f97]"></div> Very Unhealthy (201–300)</div>
                    <div className="flex items-center gap-2"><div className="w-4 h-3 rounded bg-[#7e0023]"></div> Hazardous (301+)</div>
                </div>
            ) : (
                <div className="space-y-1">
                    {[0, 0.25, 0.5, 0.75, 1].map(t => {
                        const val = scale.min + (scale.max - scale.min) * t;
                        const color = valueToColor(val, field);
                        return (
                            <div key={t} className="flex items-center gap-2">
                                <div className="w-4 h-3 rounded" style={{ backgroundColor: color }}></div>
                                {Math.round(val)} {scale.unit}
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    );
};


import { apiClient } from '../../api/client';

// ... (keep existing imports)

const MapView = () => {
    // State
    const [mode, setMode] = useState<'heatmap' | 'contours' | 'points'>('heatmap');
    const [field, setField] = useState('aqi_value');
    const [opacity, setOpacity] = useState(50);
    const [resolution, setResolution] = useState(30);
    const [geoJsonData, setGeoJsonData] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [heatmapUrl, setHeatmapUrl] = useState<string | null>(null);
    const [heatmapBounds, setHeatmapBounds] = useState<L.LatLngBoundsExpression | null>(null);

    // New Layers State
    const [devices, setDevices] = useState<any[]>([]);
    const [hotspots, setHotspots] = useState<any[]>([]);
    const [showDevices, setShowDevices] = useState(true);
    const [showHotspots, setShowHotspots] = useState(true);

    // Fetch Data
    useEffect(() => {
        const loadZones = async () => {
            setLoading(true);
            try {
                const url = `${API_BASE}/api/zones?mode=${mode}&field=${field}&resolution=${resolution}&radius=500&limit=300`;
                const resp = await fetch(url);
                const json = await resp.json();
                if (json.ok && json.geojson) {
                    setGeoJsonData(json.geojson);
                }
            } catch (err) {
                console.error("Failed to fetch zones", err);
            } finally {
                setLoading(false);
            }
        };

        const loadOverlays = async () => {
            try {
                const [devs, hots] = await Promise.all([
                    apiClient.getDevices(),
                    apiClient.getActiveHotspots()
                ]);
                setDevices(devs);
                setHotspots(hots);
            } catch (err) {
                console.error("Failed to fetch overlays", err);
            }
        };

        const debounce = setTimeout(() => {
            loadZones();
            loadOverlays();
        }, 500);

        // Poll for updates every 30s
        const interval = setInterval(loadOverlays, 30000);

        return () => {
            clearTimeout(debounce);
            clearInterval(interval);
        };
    }, [mode, field, resolution]);

    // Generate Heatmap Image
    useEffect(() => {
        if (mode !== 'heatmap' || !geoJsonData || !geoJsonData.features) {
            setHeatmapUrl(null);
            return;
        }

        const meta = geoJsonData.metadata || {};
        const bounds = meta.bounds;
        if (!bounds) return;

        const features = geoJsonData.features;
        const res = meta.grid_resolution || resolution;

        // Grid setup
        const latMin = bounds.lat_min, latMax = bounds.lat_max;
        const lonMin = bounds.lon_min, lonMax = bounds.lon_max;
        const dlat = (latMax - latMin) / res;
        const dlon = (lonMax - lonMin) / res;

        // Fill Grid
        const grid = Array.from({ length: res }, () => new Float32Array(res).fill(NaN));

        features.forEach((f: any) => {
            // simplified centroid logic
            if (f.geometry.type === 'Polygon') {
                const coords = f.geometry.coordinates[0];
                const cLon = (coords[0][0] + coords[2][0]) / 2;
                const cLat = (coords[0][1] + coords[2][1]) / 2;
                const row = Math.round((cLat - latMin - dlat / 2) / dlat);
                const col = Math.round((cLon - lonMin - dlon / 2) / dlon);
                if (row >= 0 && row < res && col >= 0 && col < res) {
                    grid[row][col] = f.properties.value;
                }
            }
        });

        // Create Canvas
        const tinyCanvas = document.createElement('canvas');
        tinyCanvas.width = res;
        tinyCanvas.height = res;
        const ctx = tinyCanvas.getContext('2d');
        if (!ctx) return;
        const imgData = ctx.createImageData(res, res);

        for (let row = 0; row < res; row++) {
            for (let col = 0; col < res; col++) {
                const val = grid[row][col];
                const pxIdx = ((res - 1 - row) * res + col) * 4; // flip Y
                if (isNaN(val)) {
                    imgData.data[pxIdx + 3] = 0;
                } else {
                    const hex = valueToColor(val, field);
                    const r = parseInt(hex.slice(1, 3), 16);
                    const g = parseInt(hex.slice(3, 5), 16);
                    const b = parseInt(hex.slice(5, 7), 16);
                    imgData.data[pxIdx] = r;
                    imgData.data[pxIdx + 1] = g;
                    imgData.data[pxIdx + 2] = b;
                    imgData.data[pxIdx + 3] = 255; // Full opacity on canvas, controlled by ImageOverlay opacity
                }
            }
        }
        ctx.putImageData(imgData, 0, 0);

        // Upscale
        const scale = 16;
        const bigCanvas = document.createElement('canvas');
        bigCanvas.width = res * scale;
        bigCanvas.height = res * scale;
        const bigCtx = bigCanvas.getContext('2d');
        if (bigCtx) {
            bigCtx.imageSmoothingEnabled = true;
            bigCtx.imageSmoothingQuality = 'high';
            bigCtx.drawImage(tinyCanvas, 0, 0, bigCanvas.width, bigCanvas.height);
            setHeatmapUrl(bigCanvas.toDataURL());
            setHeatmapBounds([[latMin, lonMin], [latMax, lonMax]]);
        }

    }, [geoJsonData, mode, field, resolution]);

    return (
        <div className="relative w-full h-full bg-gray-50 flex flex-col">
            {/* Control Panel */}
            <div className="absolute top-4 left-4 z-[1000] bg-white p-4 rounded-xl shadow-lg border border-gray-100 w-72">
                <h2 className="text-sm font-bold text-gray-800 mb-4 flex items-center gap-2">
                    <span className="text-lg">🌿</span> GreenRoute Mesh
                </h2>

                <div className="space-y-4">
                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Metric</label>
                        <select
                            value={field}
                            onChange={(e) => setField(e.target.value)}
                            className="w-full text-sm p-2 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-nature-fern"
                        >
                            {Object.entries(FIELD_SCALES).map(([key, scale]) => (
                                <option key={key} value={key}>{scale.label} ({scale.unit || 'Index'})</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">View Mode</label>
                        <div className="flex bg-gray-100 rounded-lg p-1">
                            {['heatmap', 'contours', 'points'].map((m) => (
                                <button
                                    key={m}
                                    onClick={() => setMode(m as any)}
                                    className={`flex-1 py-1.5 text-xs font-bold rounded-md transition-colors ${mode === m ? 'bg-white shadow-sm text-nature-fern' : 'text-gray-500 hover:text-gray-700'
                                        }`}
                                >
                                    {m.charAt(0).toUpperCase() + m.slice(1)}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Layers</label>
                        <div className="space-y-2">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={showDevices}
                                    onChange={(e) => setShowDevices(e.target.checked)}
                                    className="accent-nature-fern w-4 h-4 rounded border-gray-300"
                                />
                                <span className="text-sm text-gray-700">Show Devices</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={showHotspots}
                                    onChange={(e) => setShowHotspots(e.target.checked)}
                                    className="accent-red-500 w-4 h-4 rounded border-gray-300"
                                />
                                <span className="text-sm text-gray-700">Show Hotspots</span>
                            </label>
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">
                            Opacity ({opacity}%)
                        </label>
                        <input
                            type="range"
                            min="10"
                            max="100"
                            value={opacity}
                            onChange={(e) => setOpacity(parseInt(e.target.value))}
                            className="w-full accent-nature-fern h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-gray-500 uppercase mb-1">Grid Resolution</label>
                        <select
                            value={resolution}
                            onChange={(e) => setResolution(parseInt(e.target.value))}
                            className="w-full text-sm p-2 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-nature-fern"
                        >
                            <option value="15">Low (15×15)</option>
                            <option value="30">Medium (30×30)</option>
                            <option value="50">High (50×50)</option>
                            <option value="70">Ultra (70×70)</option>
                        </select>
                    </div>
                </div>

                {loading && <div className="mt-4 text-xs text-nature-fern animate-pulse font-medium">Updating map data...</div>}
            </div>

            {/* Map */}
            <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} style={{ height: '100%', width: '100%' }} zoomControl={false}>
                <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                />

                {/* Hotspots Layer */}
                {showHotspots && hotspots.map((h, i) => (
                    <CircleMarker
                        key={`hotspot-${i}`}
                        center={[h.latitude, h.longitude]}
                        radius={20}
                        pathOptions={{
                            fillColor: '#ef4444',
                            fillOpacity: 0.2,
                            color: '#ef4444',
                            weight: 2,
                            dashArray: '5, 5'
                        }}
                    >
                        <Popup>
                            <div className="text-xs font-bold text-red-600">Hotspot Detected</div>
                            <div className="text-xs">AQI: {h.avg_aqi?.toFixed(0) ?? 'N/A'}</div>
                        </Popup>
                    </CircleMarker>
                ))}

                {/* Devices Layer */}
                {showDevices && devices.map((d, i) => (
                    <CircleMarker
                        key={`device-${i}`}
                        center={[
                            d.latest_reading?.latitude || d.device.static_latitude || 0,
                            d.latest_reading?.longitude || d.device.static_longitude || 0
                        ]}
                        radius={8}
                        pathOptions={{
                            fillColor: d.latest_reading ? valueToColor(d.latest_reading.aqi_value, 'aqi_value') : '#888',
                            fillOpacity: 1,
                            color: '#fff',
                            weight: 2,
                            opacity: 1
                        }}
                    >
                        <Popup>
                            <div className="text-xs font-bold">{d.device.name}</div>
                            <div className="text-xs">ID: {d.device.device_id}</div>
                            {d.latest_reading ? (
                                <div className="text-xs mt-1">
                                    AQI: <strong>{d.latest_reading.aqi_value}</strong><br />
                                    PM2.5: {d.latest_reading.pm25_ugm3} µg/m³
                                </div>
                            ) : (
                                <div className="text-xs mt-1 text-gray-500">No recent data</div>
                            )}
                        </Popup>
                    </CircleMarker>
                ))}

                {/* Heatmap Layer */}
                {mode === 'heatmap' && heatmapUrl && heatmapBounds && (
                    <ImageOverlay
                        url={heatmapUrl}
                        bounds={heatmapBounds}
                        opacity={opacity / 100}
                    />
                )}

                {/* Contours Layer */}
                {mode === 'contours' && geoJsonData && (
                    <GeoJSON
                        key={`contours-${field}-${opacity}`} // force re-render on style change
                        data={geoJsonData}
                        style={(feature) => ({
                            fillColor: feature?.properties.color,
                            fillOpacity: (opacity / 100) * 0.6,
                            color: feature?.properties.color,
                            weight: 1,
                            opacity: (opacity / 100) * 0.8
                        })}
                    />
                )}

                {/* Points Layer */}
                {mode === 'points' && geoJsonData && geoJsonData.features && (
                    <>
                        {geoJsonData.features.map((f: any, i: number) => {
                            // Calculate centroid for Polygon geometry
                            let lat = 0, lon = 0;
                            if (f.geometry.type === 'Polygon') {
                                const coords = f.geometry.coordinates[0];
                                // Centroid of polygon (average of vertices)
                                coords.forEach((c: number[]) => { lon += c[0]; lat += c[1]; });
                                lon /= coords.length;
                                lat /= coords.length;
                            } else if (f.geometry.type === 'Point') {
                                lon = f.geometry.coordinates[0];
                                lat = f.geometry.coordinates[1];
                            }
                            
                            if (lat === 0 && lon === 0) return null;
                            
                            return (
                                <CircleMarker
                                    key={i}
                                    center={[lat, lon]}
                                    radius={6}
                                    pathOptions={{
                                        fillColor: valueToColor(f.properties.value, field),
                                        fillOpacity: opacity / 100,
                                        color: '#fff',
                                        weight: 1,
                                        opacity: 0.9
                                    }}
                                >
                                    <Popup>
                                        <div className="text-xs">
                                            <strong>{FIELD_SCALES[field].label}:</strong> {f.properties.value?.toFixed(1) ?? 'N/A'} {FIELD_SCALES[field].unit}
                                        </div>
                                    </Popup>
                                </CircleMarker>
                            );
                        })}
                    </>
                )}
            </MapContainer>

            <Legend field={field} />
        </div>
    );
};

export default MapView;
