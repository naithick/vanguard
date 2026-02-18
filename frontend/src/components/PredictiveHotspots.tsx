import { useState, useEffect } from 'react';
import { MoreHorizontal, Flame } from 'lucide-react';
import { BarChart, Bar, XAxis, ResponsiveContainer, Cell } from 'recharts';
import { apiClient } from '../api/client';

interface Hotspot {
  id: string;
  avg_aqi: number;
  severity: string;
  center_lat: number;
  center_lon: number;
  radius_m: number;
  created_at: string;
}

const PredictiveHotspots = () => {
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHotspots = async () => {
      try {
        const data = await apiClient.getActiveHotspots();
        setHotspots(data);
      } catch (err) {
        console.error('Failed to fetch hotspots:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchHotspots();
    const interval = setInterval(fetchHotspots, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Convert hotspots to chart data
  const data = hotspots.length > 0 
    ? hotspots.slice(0, 7).map((hs, idx) => ({
        label: `H${idx + 1}`,
        level: hs.avg_aqi,
        severity: hs.severity
      }))
    : [
        { label: '6AM', level: 0 },
        { label: '9AM', level: 0 },
        { label: '12PM', level: 0 },
        { label: '3PM', level: 0 },
        { label: '6PM', level: 0 },
      ];

  const getBarColor = (value: number) => {
    if (value < 50) return 'var(--primary-400)';
    if (value < 100) return 'var(--primary-500)';
    if (value < 150) return 'var(--primary-600)';
    return 'var(--primary-800)';
  };

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-600 flex items-center gap-2">
          <Flame className="w-4 h-4 text-orange-500" />
          Active Hotspots
        </h3>
        <span className={`text-[10px] px-2 py-0.5 rounded-full ${hotspots.length > 0 ? 'bg-orange-100 text-orange-600' : 'bg-gray-100 text-gray-500'}`}>
          {hotspots.length} Active
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mb-3 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-primary-400 rounded-sm"></div>
          <span className="text-gray-500">Good</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-primary-500 rounded-sm"></div>
          <span className="text-gray-500">Moderate</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-primary-800 rounded-sm"></div>
          <span className="text-gray-500">Unhealthy</span>
        </div>
      </div>

      {/* Bar Chart */}
      <div className="h-28">
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-400 text-xs">
            Loading hotspots...
          </div>
        ) : hotspots.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            <Flame className="w-6 h-6 mb-1 opacity-30" />
            <span className="text-xs">No active hotspots</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barSize={14}>
              <XAxis
                dataKey="label"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 8, fill: '#9ca3af' }}
              />
              <Bar dataKey="level" radius={[2, 2, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={getBarColor(entry.level)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};

export default PredictiveHotspots;
