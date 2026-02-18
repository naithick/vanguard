import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip, Cell } from 'recharts';
import { Activity } from 'lucide-react';
import type { Reading } from '../api/client';

interface PollutantLevelsProps {
  readings?: Reading[];
}

const PollutantLevels = ({ readings = [] }: PollutantLevelsProps) => {
  // Show PM2.5 and CO2 for the last 8 readings (cleaner look)
  const data = readings.slice(0, 8).reverse().map(r => ({
    time: new Date(r.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    pm25: r.pm25_ugm3,
    co2: r.co2_ppm / 10, // Scaled for visual comparison
    co: r.co_ppm,
    raw_co2: r.co2_ppm
  }));

  const getBarColor = (val: number) => {
    if (val < 15) return '#E1F0D6'; // Foam (Lightest)
    if (val < 35) return '#9FE870'; // Wise Lime (Bright)
    if (val < 55) return '#22C55E'; // Nature Fern (Standard)
    return '#14B8A6'; // Nature Teal (Cool)
  };

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="bg-primary-100 p-1.5 rounded-lg text-primary-600">
            <Activity size={14} />
          </div>
          <h3 className="text-sm font-bold text-gray-700 font-mono tracking-tight uppercase">Air Vitality</h3>
        </div>
        <div className="text-[10px] text-primary-600/50 font-bold uppercase tracking-widest">Real-time Node Telemetry</div>
      </div>

      <div className="flex-1 min-h-[140px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barGap={4}>
            <XAxis
              dataKey="time"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 9, fill: '#94a3b8' }}
              interval={0}
            />
            <Tooltip
              contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 8px 24px rgba(0,0,0,0.1)', fontSize: '11px' }}
              cursor={{ fill: 'rgba(240, 244, 240, 0.4)' }}
            />
            <Bar
              dataKey="pm25"
              name="PM2.5 (µg/m³)"
              radius={[4, 4, 0, 0]}
              barSize={18}
            >
              {data.map((entry, index) => (
                <Cell key={`pm25-${index}`} fill={getBarColor(entry.pm25)} />
              ))}
            </Bar>
            <Bar
              dataKey="co2"
              name="CO₂ (Scaled)"
              fill="#D97706"
              radius={[4, 4, 0, 0]}
              barSize={12}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <div className="bg-gray-50 rounded-lg p-2 text-center">
          <div className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">PM2.5</div>
          <div className="text-xs font-bold text-gray-700">{readings[0]?.pm25_ugm3.toFixed(1) ?? '--'}</div>
        </div>
        <div className="bg-gray-50 rounded-lg p-2 text-center">
          <div className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">CO₂</div>
          <div className="text-xs font-bold text-gray-700">{readings[0]?.co2_ppm.toFixed(0) ?? '--'}</div>
        </div>
        <div className="bg-primary-50 rounded-lg p-2 text-center text-primary-600">
          <div className="text-[10px] text-primary-400 font-bold uppercase tracking-tighter">Status</div>
          <div className="text-[10px] font-bold truncate uppercase">{readings[0]?.aqi_category ?? 'OFFLINE'}</div>
        </div>
      </div>
    </div>
  );
};

export default PollutantLevels;
