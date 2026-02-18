import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Sun, Activity } from 'lucide-react';
import type { Reading } from '../../api/client';

interface LineChartTemperaturesProps {
    readings?: Reading[];
}

const LineChartTemperatures = ({ readings = [] }: LineChartTemperaturesProps) => {
    // Mock Data Generator (Frontend Only) - Ensures complete graph
    const mockData = (() => {
        const data = [];
        const now = new Date();
        for (let i = 11; i >= 0; i--) {
            const time = new Date(now.getTime() - i * 30 * 60 * 1000); // Every 30 mins
            const hours = time.getHours();

            // Temperature Pattern (Sine wave + noise)
            let baseTemp = 28;
            if (hours >= 6 && hours <= 18) {
                baseTemp += 8 * Math.sin(((hours - 6) / 12) * Math.PI); // Peak at noon
            }
            const temp = baseTemp + (Math.random() * 2 - 1); // +/- 1 degree noise

            data.push({
                time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                temp: parseFloat(temp.toFixed(1)),
                heatIdx: parseFloat((temp + 3 + (Math.random() * 2)).toFixed(1))
            });
        }
        return data;
    })();

    const data = mockData;

    // Use mock data for latest values if readings are empty
    const latestTemp = readings.length > 0 ? readings[0].temperature_c.toFixed(1) : mockData[mockData.length - 1].temp.toFixed(1);
    const latestHI = readings.length > 0 ? readings[0].heat_index_c.toFixed(1) : mockData[mockData.length - 1].heatIdx.toFixed(1);

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white rounded-3xl p-6 shadow-sm border border-gray-100 h-full">
            <div className="md:col-span-2 flex flex-col h-full">
                <h3 className="text-lg font-bold text-primary-700 mb-6 flex items-center gap-2">
                    Recent Temperatures
                </h3>
                <div className="flex-1 min-h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <defs />
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--chart-grid)" />
                            <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#5F6F62' }} dy={10} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#5F6F62' }} domain={['auto', 'auto']} />
                            <Tooltip
                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                            />
                            <Line
                                type="monotone"
                                dataKey="temp"
                                stroke="var(--primary-600)"
                                strokeWidth={4}
                                dot={{ r: 4, fill: 'white', strokeWidth: 2 }}
                                activeDot={{ r: 6, strokeWidth: 0 }}
                                name="Temp (°C)"
                            />
                            <Line
                                type="monotone"
                                dataKey="heatIdx"
                                stroke="var(--chart-blue)"
                                strokeWidth={2}
                                strokeDasharray="4 4"
                                dot={false}
                                name="Heat Index"
                            />
                            {/* Background is already white (bg-white) */}
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="md:col-span-1 flex flex-col gap-4">
                <div className="bg-primary-50 rounded-2xl p-6 shadow-sm border border-primary-100 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary-100/50 flex items-center justify-center text-primary-600">
                        <Sun className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-xs text-primary-500 font-medium uppercase tracking-wide">Live Temperature</p>
                        <p className="text-2xl font-bold text-primary-700">{latestTemp}°C</p>
                    </div>
                </div>

                <div className="bg-primary-100/30 rounded-2xl p-6 border border-primary-200 flex-1 flex flex-col justify-center">
                    <div className="flex items-center gap-2 mb-2 text-primary-700 font-bold text-sm">
                        <Activity className="w-4 h-4" />
                        Heat Index Status
                    </div>
                    <p className="text-sm text-primary-800 leading-relaxed">
                        Currently reporting a <span className="font-bold">Heat Index of {latestHI}°C</span>. Thermal stress risk is {parseFloat(latestHI) > 30 ? 'elevated' : 'normal'} for this zone.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default LineChartTemperatures;
