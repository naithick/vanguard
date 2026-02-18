import { MoreHorizontal } from 'lucide-react';
import { BarChart, Bar, XAxis, ResponsiveContainer, Cell } from 'recharts';

const PredictiveHotspots = () => {
  const data = [
    { hour: '6AM', level: 20 },
    { hour: '8AM', level: 35 },
    { hour: '10AM', level: 45 },
    { hour: '12PM', level: 60 },
    { hour: '2PM', level: 75 },
    { hour: '4PM', level: 55 },
    { hour: '6PM', level: 40 },
  ];

  const getBarColor = (value: number) => {
    if (value < 30) return 'var(--primary-400)';
    if (value < 50) return 'var(--primary-500)';
    if (value < 70) return 'var(--primary-600)';
    return 'var(--primary-800)';
  };

  return (
    <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-gray-600">Predictive Hotspots</h3>
        <button className="text-gray-400 hover:text-primary-600 transition-colors">
          <MoreHorizontal className="w-4 h-4" />
        </button>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mb-3 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-primary-400 rounded-sm"></div>
          <span className="text-gray-500">Clean Air</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-primary-500 rounded-sm"></div>
          <span className="text-gray-500">Average</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-primary-800 rounded-sm"></div>
          <span className="text-gray-500">Harm</span>
        </div>
      </div>

      {/* Bar Chart */}
      <div className="h-28">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barSize={14}>
            <XAxis
              dataKey="hour"
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
      </div>
    </div>
  );
};

export default PredictiveHotspots;
