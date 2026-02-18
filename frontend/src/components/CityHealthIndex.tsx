import { Activity, TrendingUp, Maximize2 } from 'lucide-react';
import type { Reading } from '../api/client';

interface CityHealthIndexProps {
  reading?: Reading | null;
  device?: any;
}

const CityHealthIndex = ({ reading, device }: CityHealthIndexProps) => {
  const healthIndex = reading?.aqi_value ?? 0;
  const deviceName = device?.name ?? 'City';
  const radius = 55;
  const circumference = 2 * Math.PI * radius;
  const percentage = Math.min((healthIndex / 500) * 100, 100);
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  // AQI-based colors (Modern Blue Theme)
  // Wise Theme AQI Colors
  const getAQIColor = (aqi: number) => {
    // Good: Foam -> Lime
    if (aqi <= 50) return { from: '#E1F0D6', to: '#9FE870', text: 'text-primary-700', bg: 'border-primary-200' };
    // Moderate: Lime -> Sage
    if (aqi <= 100) return { from: '#9FE870', to: '#5F6F62', text: 'text-primary-800', bg: 'border-primary-300' };
    // Unhealthy: Sage -> Forest
    if (aqi <= 150) return { from: '#5F6F62', to: '#163300', text: 'text-primary-900', bg: 'border-primary-400' };
    // Very Unhealthy: Forest -> Dark Forest
    if (aqi <= 200) return { from: '#163300', to: '#0D2000', text: 'text-primary-950', bg: 'border-primary-500' };
    // Hazardous: Deep Forest
    if (aqi <= 300) return { from: '#0D2000', to: '#050D00', text: 'text-primary-950', bg: 'border-primary-600' };
    // Off user charts
    return { from: '#050D00', to: '#000000', text: 'text-slate-950', bg: 'border-slate-800' };
  };

  const colors = getAQIColor(healthIndex);

  // Pollutant values
  const pm25 = reading?.pm25_ugm3?.toFixed(1) ?? '--';
  const co = reading?.co_ppm?.toFixed(1) ?? '--';
  const co2 = reading?.co2_ppm?.toFixed(0) ?? '--';
  const gas = reading?.gas_resistance ? (reading.gas_resistance / 1000).toFixed(1) + 'k' : '--';

  // Labels
  const aqiCategory = reading?.aqi_category ?? 'No Data';
  const respiratoryRisk = reading?.respiratory_risk_label ?? '--';

  return (
    <div className="relative rounded-2xl overflow-hidden h-full shadow-sm border border-gray-100 group min-h-[300px]">

      {/* CSS Modern Blue Background Layer */}
      <div
        className="absolute inset-0 transition-transform duration-700 group-hover:scale-105"
        style={{
          background: `
                radial-gradient(circle at 10% 20%, rgba(159, 232, 112, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(22, 51, 0, 0.08) 0%, transparent 40%),
                linear-gradient(135deg, #ffffff 0%, #F2F5F7 100%)
            `
        }}
      >
        <div className="absolute top-[-50%] left-[-20%] w-[80%] h-[80%] bg-primary-100/20 rounded-full blur-3xl"></div>
        <div className="absolute bottom-[-20%] right-[-20%] w-[60%] h-[60%] bg-primary-200/20 rounded-full blur-3xl"></div>
      </div>

      {/* Content Overlay */}
      <div className="absolute inset-0 bg-white/40 backdrop-blur-[1px]"></div>

      {/* Main Content Container */}
      <div className="relative z-10 p-4 h-full flex flex-col">

        {/* Header */}
        <div className="flex justify-between items-center mb-2">
          <h3 className="text-sm font-semibold text-gray-700 tracking-wide uppercase">{deviceName} Health Index</h3>
          <div className="flex items-center gap-2 bg-white/80 px-2 py-1 rounded-full border border-primary-100 shadow-sm">
            <div className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary-500"></span>
            </div>
            <span className="text-[10px] font-bold text-primary-700 uppercase tracking-wider">Live</span>
          </div>
        </div>

        {/* Main Gauge Container */}
        <div className="relative w-32 h-32 mx-auto mb-2 flex-shrink-0">
          <svg className="w-full h-full transform -rotate-90 drop-shadow-md">
            <circle cx="50%" cy="50%" r={radius} fill="none" stroke="#ffffff" strokeWidth="10" strokeLinecap="round" className="opacity-60" />
            <circle
              cx="50%"
              cy="50%"
              r={radius}
              fill="none"
              stroke="url(#healthGradient)"
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              className="transition-all duration-1000 ease-out"
            />
            <defs>
              <linearGradient id="healthGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor={colors.from} />
                <stop offset="100%" stopColor={colors.to} />
              </linearGradient>
            </defs>
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-4xl font-bold text-gray-800 tracking-tight">{healthIndex}</span>
            <span className="text-[10px] font-semibold text-gray-500 bg-white/80 px-2 py-0.5 rounded-full mt-1 border border-gray-100">US AQI</span>
          </div>
        </div>

        {/* AQI Category + Respiratory Risk */}
        <div className="flex justify-center gap-3 mb-3">
          <span className={`text-xs font-bold px-3 py-1 rounded-full bg-white/90 border ${colors.bg} ${colors.text}`}>
            {aqiCategory}
          </span>
          <span className="text-xs font-bold px-3 py-1 rounded-full bg-white/90 border border-gray-200 text-gray-600">
            Risk: {respiratoryRisk}
          </span>
        </div>

        {/* Live Monitors */}
        <div className="flex-1 flex flex-col justify-center mb-2">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 text-center">Live Monitors</div>

          <div className="flex justify-around items-center">
            {/* PM2.5 */}
            <div className="flex flex-col items-center gap-1 group/item">
              <div className="text-[10px] font-bold text-gray-500">PM2.5</div>
              <div className="bg-white/90 text-primary-700 px-3 py-1.5 rounded-lg text-xs font-bold border border-primary-100 shadow-sm group-hover/item:-translate-y-1 transition-transform">
                {pm25} µg
              </div>
            </div>

            {/* CO */}
            <div className="flex flex-col items-center gap-1 group/item">
              <div className="text-[10px] font-bold text-gray-500">CO</div>
              <div className="bg-white/90 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-bold border border-gray-100 shadow-sm group-hover/item:-translate-y-1 transition-transform">
                {co} ppm
              </div>
            </div>

            {/* CO₂ */}
            <div className="flex flex-col items-center gap-1 group/item">
              <div className="text-[10px] font-bold text-gray-500">CO₂</div>
              <div className="bg-white/90 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-bold border border-gray-100 shadow-sm group-hover/item:-translate-y-1 transition-transform">
                {co2} ppm
              </div>
            </div>

            {/* Gas */}
            <div className="flex flex-col items-center gap-1 group/item">
              <div className="text-[10px] font-bold text-gray-500">Gas</div>
              <div className="bg-white/90 text-gray-700 px-3 py-1.5 rounded-lg text-xs font-bold border border-gray-100 shadow-sm group-hover/item:-translate-y-1 transition-transform">
                {gas} Ω
              </div>
            </div>
          </div>
        </div>

        {/* Footer Metrics */}
        <div className="w-full pt-3 border-t border-gray-200/50 flex items-center justify-between mt-auto">
          <div className="flex items-center gap-2">
            <Activity className="w-3.5 h-3.5 text-gray-400" />
            <span className="text-[10px] font-mono text-gray-500">ID: {reading?.device_id?.substring(0, 8) || 'Scanning...'}</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-3.5 h-3.5 text-primary-600" />
            <span className="text-[10px] text-primary-700 font-bold">{reading ? 'Online' : 'Waiting...'}</span>
            <Maximize2 className="w-3.5 h-3.5 text-gray-400 ml-1" />
          </div>
        </div>

      </div>
    </div>
  );
};

export default CityHealthIndex;
