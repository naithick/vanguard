import { Thermometer, Navigation as NavIcon, Sun, Cloud } from 'lucide-react';
import type { Reading } from '../api/client';

interface WeatherDetailsProps {
  reading?: Reading | null;
}

const WeatherDetails = ({ reading }: WeatherDetailsProps) => {
  const feelsLike = reading?.heat_index_c?.toFixed(1) ?? '--';
  const humidity = reading?.humidity_pct?.toFixed(0) ?? '--';
  const pressure = reading?.pressure_hpa?.toFixed(0) ?? '--';

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
      {/* Heat Index */}
      <div className="flex items-start gap-3 mb-6">
        <div className="w-10 h-10 bg-primary-100/50 rounded-xl flex items-center justify-center">
          <Thermometer className="w-5 h-5 text-primary-600" />
        </div>
        <div>
          <div className="text-xs text-gray-500">Heat Index</div>
          <div className="text-lg font-semibold text-gray-800">{feelsLike}°C</div>
          <div className="text-sm text-primary-600">{reading?.temperature_c?.toFixed(1) ?? '--'}°C Amb.</div>
        </div>
      </div>

      {/* Atmospheric */}
      <div className="flex items-start gap-3 mb-6">
        <div className="w-10 h-10 bg-primary-100/40 rounded-xl flex items-center justify-center">
          <NavIcon className="w-5 h-5 text-primary-500" />
        </div>
        <div>
          <div className="text-xs text-gray-500">Pressure</div>
          <div className="text-lg font-semibold text-gray-800">{pressure} hPa</div>
          <div className="text-sm text-primary-500">{humidity}% Hum.</div>
        </div>
      </div>

      {/* Environmental Context */}
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-gray-100">
        <div className="text-center">
          <Sun className="w-6 h-6 text-yellow-500 mx-auto mb-2" />
          <div className="text-xs text-gray-500">Condition</div>
          <div className="text-lg font-semibold text-gray-800">{parseFloat(feelsLike) > 30 ? 'Warm' : 'Mild'}</div>
          <div className="text-[10px] text-gray-400">Sensor Live</div>
        </div>
        <div className="text-center">
          <Cloud className="w-6 h-6 text-orange-400 mx-auto mb-2" />
          <div className="text-xs text-gray-500">Status</div>
          <div className="text-lg font-semibold text-gray-800">{reading?.weather_condition || 'Clear'}</div>
          <div className="text-[10px] text-gray-400">Mesh Sync</div>
        </div>
      </div>
    </div>
  );
};

export default WeatherDetails;
