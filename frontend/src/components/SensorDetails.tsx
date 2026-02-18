import type { Reading } from '../api/client';

interface SensorDetailsProps {
  reading?: Reading | null;
}

const SensorDetails = ({ reading }: SensorDetailsProps) => {
  const sensors = [
    { label: 'PM2.5', value: reading?.pm25_ugm3 != null ? `${reading.pm25_ugm3.toFixed(1)} µg/m³` : '--', status: 'normal' },
    { label: 'CO', value: reading?.co_ppm != null ? `${reading.co_ppm.toFixed(2)} ppm` : '--', status: 'normal' },
    { label: 'CO₂', value: reading?.co2_ppm != null ? `${reading.co2_ppm.toFixed(1)} ppm` : '--', status: 'normal' },
    { label: 'AQI', value: reading?.aqi_value != null ? `${reading.aqi_value} (${reading.aqi_category || ''})` : '--', status: 'normal' },
    { label: 'Gas Res.', value: reading?.gas_resistance ? `${(reading.gas_resistance / 1000).toFixed(1)} kΩ` : '--', status: 'normal' },
    { label: 'Temp', value: reading?.temperature_c != null ? `${reading.temperature_c.toFixed(1)} °C` : '--', status: 'normal' },
    { label: 'Heat Index', value: reading?.heat_index_c != null ? `${reading.heat_index_c.toFixed(1)} °C` : '--', status: 'normal' },
    { label: 'Humidity', value: reading?.humidity_pct != null ? `${reading.humidity_pct.toFixed(1)} %` : '--', status: 'normal' },
    { label: 'Pressure', value: reading?.pressure_hpa != null ? `${reading.pressure_hpa.toFixed(1)} hPa` : '--', status: 'normal' },
    { label: 'Toxic Gas Idx', value: reading?.toxic_gas_index != null ? `${reading.toxic_gas_index}` : '--', status: 'normal' },
    { label: 'Respiratory', value: reading?.respiratory_risk_label || '--', status: reading?.respiratory_risk_label === 'High' || reading?.respiratory_risk_label === 'Very High' || reading?.respiratory_risk_label === 'Severe' ? 'warning' : 'normal' },
    { label: 'Device ID', value: reading?.device_id || 'Searching...', status: reading ? 'normal' : 'warning' },
    { label: 'Recorded', value: reading?.recorded_at ? new Date(reading.recorded_at).toLocaleTimeString() : '--', status: 'normal' },
  ];

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm">
      <h3 className="text-sm font-medium text-gray-600 mb-4">Sensor Details</h3>

      {/* Sensor List */}
      <div className="space-y-3">
        {sensors.map((sensor, index) => (
          <div key={index} className="flex justify-between items-center">
            <span className="text-sm text-gray-500">{sensor.label}</span>
            <span className={`text-sm font-medium ${sensor.status === 'warning' ? 'text-status-warning' : 'text-gray-800'}`}>
              {sensor.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SensorDetails;
