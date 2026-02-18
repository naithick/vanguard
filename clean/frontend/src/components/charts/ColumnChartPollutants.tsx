import { BarChart, Bar, XAxis, ResponsiveContainer, Tooltip, Cell, CartesianGrid } from 'recharts';
import { Clock, Info } from 'lucide-react';
import type { Reading } from '../../api/client';

interface ColumnChartPollutantsProps {
    readings?: Reading[];
}

const ColumnChartPollutants = ({ readings = [] }: ColumnChartPollutantsProps) => {
    // Group readings by day of the week (last 7 days)
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    // In a real scenario, we might want to aggregate by day. 
    // For now, let's just take the last 7 distinct observations for visual variety, 
    // or map the last 7 readings.
    const chartData = readings.slice(0, 7).reverse().map(r => ({
        day: days[new Date(r.recorded_at).getDay()],
        value: Math.round(r.aqi_value)
    }));

    // If no readings, show some empty bars
    const data = chartData.length > 0 ? chartData : days.map(d => ({ day: d, value: 0 }));

    const avgValue = data.length > 0
        ? Math.round(data.reduce((acc, curr) => acc + curr.value, 0) / data.length)
        : 0;

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white rounded-3xl p-6 shadow-sm border border-gray-100 h-full">
            {/* Left Column: Chart Area (2/3 width) */}
            <div className="md:col-span-2 flex flex-col h-full">
                <h3 className="text-lg font-bold text-primary-700 mb-6 flex items-center gap-2">
                    Weekly Trends (Pollutants)
                </h3>
                <div className="flex-1 min-h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={data} barSize={40}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                            <XAxis
                                dataKey="day"
                                axisLine={false}
                                tickLine={false}
                                tick={{ fontSize: 12, fill: '#5F6F62' }}
                                dy={10}
                            />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                            />
                            <Bar
                                dataKey="value"
                                radius={[4, 4, 0, 0]}
                                name="AQI Level"
                            >
                                {data.map((entry, index) => {
                                    const colors = [
                                        'var(--chart-1)', // Fern
                                        'var(--chart-2)', // Teal
                                        'var(--chart-3)', // Lime
                                        'var(--chart-4)', // Sun
                                        'var(--chart-5)'  // Earth
                                    ];
                                    return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                                })}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Right Column: Insight Area (1/3 width) */}
            <div className="md:col-span-1 flex flex-col gap-4">
                <div className="bg-primary-50 rounded-2xl p-6 shadow-sm border border-primary-100 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary-100/50 flex items-center justify-center text-primary-600">
                        <Clock className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-xs text-primary-500 font-medium uppercase tracking-wide">Weekly Average</p>
                        <p className="text-2xl font-bold text-primary-700">{avgValue} <span className="text-sm font-normal text-primary-400">AQI</span></p>
                    </div>
                </div>

                <div className="bg-primary-50/50 rounded-2xl p-6 border border-primary-100 flex-1 flex flex-col justify-center">
                    <div className="flex items-center gap-2 mb-2 text-primary-700 font-bold text-sm">
                        <Info className="w-4 h-4" />
                        Live Observation
                    </div>
                    <p className="text-sm text-primary-800 leading-relaxed">
                        Data from the mesh network shows <span className="font-bold">2 active nodes</span> reporting. {avgValue < 50 ? 'Air quality is currently within safe limits.' : 'Air quality is slightly elevated in some zones.'}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default ColumnChartPollutants;
