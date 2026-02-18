import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell, CartesianGrid } from 'recharts';
import { Wind, Fingerprint } from 'lucide-react';
import type { Reading } from '../../api/client';

interface BarChartWindProps {
    readings?: Reading[];
}

const BarChartWind = ({ readings = [] }: BarChartWindProps) => {
    // Map last 7 readings to speed data
    const data = readings.slice(0, 7).reverse().map(r => ({
        time: new Date(r.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        speed: r.speed_kmh ?? 0
    }));

    // If no readings, show empty
    const chartData = data.length > 0 ? data : [{ time: '--', speed: 0 }];

    const avgSpeed = data.length > 0
        ? (data.reduce((acc, curr) => acc + curr.speed, 0) / data.length).toFixed(1)
        : '0.0';

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white rounded-3xl p-6 shadow-sm border border-gray-100 h-full">
            {/* Left Column: Chart Area */}
            <div className="md:col-span-2 flex flex-col h-full">
                <h3 className="text-lg font-bold text-gray-800 mb-6 flex items-center gap-2">
                    Wind Velocity (Mesh)
                </h3>
                <div className="flex-1 min-h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart layout="vertical" data={chartData} margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--chart-grid)" />
                            <XAxis type="number" hide />
                            <YAxis
                                dataKey="time"
                                type="category"
                                width={60}
                                tick={{ fontSize: 10, fontWeight: 500, fill: '#64748b' }}
                                axisLine={false}
                                tickLine={false}
                            />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                            />
                            <Bar dataKey="speed" radius={[0, 4, 4, 0]} barSize={20} name="Speed (km/h)">
                                {chartData.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.speed > 10 ? '#a855f7' : '#3b82f6'} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Right Column: Insight Area */}
            <div className="md:col-span-1 flex flex-col gap-4">
                <div className="bg-primary-50 rounded-2xl p-6 shadow-sm border border-primary-100 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary-100/50 flex items-center justify-center text-primary-600">
                        <Wind className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">Recent Average</p>
                        <p className="text-2xl font-bold text-gray-800">{avgSpeed} <span className="text-sm font-normal text-gray-400">km/h</span></p>
                    </div>
                </div>

                <div className="bg-primary-50/50 rounded-2xl p-6 border border-primary-100 flex-1 flex flex-col justify-center">
                    <div className="flex items-center gap-2 mb-2 text-primary-700 font-bold text-sm">
                        <Wind className="w-4 h-4" />
                        Air Displacement
                    </div>
                    <p className="text-sm text-primary-800 leading-relaxed">
                        Data from GPS sensors indicates <span className="font-bold">stable wind patterns</span>. Mesh nodes are currently detecting a {parseFloat(avgSpeed) > 5 ? 'noticeable' : 'minimal'} air displacement in the sector.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default BarChartWind;
