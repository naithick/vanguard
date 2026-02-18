import { ArrowUpRight } from 'lucide-react';
import type { Reading } from '../api/client';

interface TemperatureReportsProps {
  reading?: Reading | null;
}

const TemperatureReports = ({ reading }: TemperatureReportsProps) => {
  // Use real sensor data to generate context-aware reports
  const reports = [
    {
      id: 'S1',
      text: reading
        ? `Node ${reading.device_id.substring(0, 8)} detecting ${reading.aqi_category} air quality with ${reading.pm25_ugm3.toFixed(1)} PM2.5.`
        : 'Scanning for mesh network nodes...',
      color: 'bg-primary-100/50 text-primary-600',
    },
    {
      id: 'S2',
      text: reading?.toxic_gas_index && reading.toxic_gas_index > 50
        ? `Elevated gas resistance detected (${(reading.gas_resistance / 1000).toFixed(1)}kΩ). AI checking for anomalies.`
        : 'All environmental sensors reporting stable baseline levels.',
      color: 'bg-primary-50 text-primary-700',
    },
  ];

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-600">Mesh Health Reports</h3>
        <button className="text-gray-400 hover:text-primary-600 transition-colors">
          <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>

      {/* Reports List */}
      <div className="space-y-4">
        {reports.map((report, index) => (
          <div key={index} className="flex items-start gap-3">
            <div className={`w-8 h-8 ${report.color} rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0`}>
              {report.id}
            </div>
            <p className="text-[11px] text-gray-600 leading-relaxed line-clamp-3">{report.text}</p>
          </div>
        ))}
      </div>

      {/* Additional Info */}
      <div className="mt-4 pt-4 border-t border-gray-100">
        <div className="flex items-center justify-between text-xs">
          <span className="text-gray-500">Sync Status</span>
          <span className="text-primary-600 font-medium">{reading ? 'Real-time' : 'Waiting...'}</span>
        </div>
      </div>
    </div>
  );
};

export default TemperatureReports;
