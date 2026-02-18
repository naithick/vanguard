import { Sun, Droplets, Thermometer } from 'lucide-react';
import type { Reading, DeviceWithReading } from '../api/client';

interface WeatherCardProps {
  selectedCity: string;
  onCityChange: (city: string) => void;
  reading?: Reading | null;
  devices?: DeviceWithReading[];
  selectedDeviceId?: string | null;
  onDeviceChange?: (deviceId: string) => void;
}

const WeatherCard = ({ reading, devices = [], selectedDeviceId, onDeviceChange }: WeatherCardProps) => {
  // Live sensor data
  const temp = reading?.temperature_c ?? null;
  const humidity = reading?.humidity_pct ?? null;
  const pressure = reading?.pressure_hpa ?? null;
  const heatIndex = reading?.heat_index_c ?? null;
  const speed = reading?.speed_kmh ?? 0;
  const deviceName = devices.find(d => d.device.device_id === selectedDeviceId)?.device.name ?? 'No Device';

  // Cycle through devices
  const currentIdx = devices.findIndex(d => d.device.device_id === selectedDeviceId);
  const goNext = () => {
    if (devices.length === 0) return;
    const next = (currentIdx + 1) % devices.length;
    onDeviceChange?.(devices[next].device.device_id);
  };
  const goPrev = () => {
    if (devices.length === 0) return;
    const prev = (currentIdx - 1 + devices.length) % devices.length;
    onDeviceChange?.(devices[prev].device.device_id);
  };

  // Determine weather icon based on temperature
  const WeatherIcon = temp && temp > 30 ? Sun : temp && temp < 20 ? Droplets : Thermometer;

  return (
    <div className="bg-gradient-to-br from-nature-bg to-nature-light rounded-3xl p-6 shadow-xl shadow-nature-fern/10 flex flex-col justify-between relative overflow-hidden border border-nature-light h-full min-h-[400px]">
      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-nature-fern/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none"></div>

      {/* Header */}
      <div className="flex justify-between items-start z-10 w-full mb-4">
        <div className="flex flex-col">
          <span className="text-xs font-bold text-primary-500 tracking-wider">LIVE</span>
          <span className="text-xs font-bold text-primary-500 tracking-wider">SENSORS</span>
        </div>
        <div className="flex items-center gap-2 bg-white/60 backdrop-blur-sm px-3 py-1.5 rounded-full border border-nature-fern/10 shadow-sm">
          <button onClick={goPrev} className="p-1 hover:bg-black/5 rounded-full transition-colors text-primary-600">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
          <div className="flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" className="text-primary-500"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" /></svg>
            <span className="text-xs font-semibold text-primary-700 truncate max-w-[150px]">{deviceName}</span>
          </div>
          <button onClick={goNext} className="p-1 hover:bg-black/5 rounded-full transition-colors text-primary-600">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6" /></svg>
          </button>
        </div>
      </div>

      {/* Main Temp */}
      <div className="flex flex-col items-center justify-center py-6 z-10 flex-1">
        <div className="relative mb-6">
          <div className="absolute inset-0 bg-nature-fern/20 blur-2xl rounded-full scale-110"></div>
          <div className="w-24 h-24 bg-white/40 rounded-full flex items-center justify-center backdrop-blur-sm shadow-inner border border-white/20 relative z-10">
            <WeatherIcon className="w-14 h-14 text-nature-sun drop-shadow-sm" />
          </div>
        </div>
        <div className="text-7xl font-bold text-primary-800 tracking-tighter mb-2">
          {temp !== null ? Math.round(temp) : '--'}°C
        </div>
        <div className="text-lg font-medium text-primary-600">
          {humidity !== null ? Math.round(humidity) : '--'}% Humidity
        </div>
      </div>

      {/* Footer Stats */}
      <div className="bg-white/60 backdrop-blur-md rounded-2xl p-4 flex items-center justify-between z-10 border border-nature-fern/10 shadow-sm mt-4">
        <div className="text-center flex-1 border-r border-nature-fern/10">
          <div className="text-xs text-primary-500 font-medium mb-1">Heat Index</div>
          <div className="text-lg font-bold text-primary-700">{heatIndex !== null ? heatIndex.toFixed(1) : '--'}°</div>
        </div>
        <div className="text-center flex-1">
          <div className="text-xs text-primary-500 font-medium mb-1">Pressure</div>
          <div className="text-lg font-bold text-primary-700">{pressure !== null ? Math.round(pressure) : '--'} hPa</div>
        </div>
      </div>
    </div>
  );
};

export default WeatherCard;
