import { ArrowUpRight } from 'lucide-react';
import type { DeviceWithReading, Stats } from '../api/client';

interface FleetStatusProps {
  devices?: DeviceWithReading[];
  stats?: Stats | null;
}

const FleetStatus = ({ devices = [], stats }: FleetStatusProps) => {
  const totalDevices = stats?.device_count ?? devices.length;
  const activeDevices = devices.filter(d => d.latest_reading !== null).length;
  const percentage = totalDevices > 0 ? Math.round((activeDevices / totalDevices) * 100) : 0;
  const circumference = 2 * Math.PI * 35;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-600">Fleet Status</h3>
        <button className="text-gray-400 hover:text-primary-600 transition-colors">
          <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>

      {/* Circular Progress */}
      <div className="flex items-center justify-center">
        <div className="relative w-24 h-24">
          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 80 80">
            {/* Background Circle */}
            <circle
              cx="40"
              cy="40"
              r="35"
              fill="none"
              stroke="#e5e7eb"
              strokeWidth="6"
            />
            {/* Progress Circle */}
            <circle
              cx="40"
              cy="40"
              r="35"
              fill="none"
              stroke="var(--primary-600)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              className="transition-all duration-1000"
            />
          </svg>

          {/* Center Text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-gray-800">{percentage}%</span>
          </div>
        </div>
      </div>

      {/* Status Text */}
      <div className="text-center mt-3">
        <div className="text-sm font-medium text-primary-600">
          {activeDevices > 0 ? 'Active' : 'No Devices'}
        </div>
        <div className="text-xs text-gray-500">
          Nodes: {activeDevices}/{totalDevices}
        </div>
      </div>
    </div>
  );
};

export default FleetStatus;
