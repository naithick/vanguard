import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, Activity } from 'lucide-react';
import type { Reading } from '../../api/client';

interface ComposedChartHotspotsProps {
    readings?: Reading[];
}

const ComposedChartHotspots = ({ readings = [] }: ComposedChartHotspotsProps) => {
    // Map readings to show AQI intensity vs PM2.5 trend
    const data = readings.slice(0, 10).reverse().map(r => ({
        time: new Date(r.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        intensity: r.aqi_value,
        pm25: r.pm25_ugm3,
        dist: r.distance_moved_m
    }));

    const latestAQI = readings.length > 0 ? readings[0].aqi_value : 0;

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white rounded-3xl p-6 shadow-sm border border-gray-100 h-full">
            <div className="md:col-span-2 flex flex-col h-full">
                <h3 className="text-lg font-bold text-primary-700 mb-6 flex items-center gap-2">
                    Predictive Node Hotspots
                </h3>
                <div className="flex-1 min-h-[250px]">
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                            <defs />
                            <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
                            <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#5F6F62' }} dy={10} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#5F6F62' }} />
                            <Tooltip
                                cursor={{ fill: '#fff1f2' }}
                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                            />
                            <Bar dataKey="intensity" barSize={24} fill="var(--primary-400)" radius={[4, 4, 0, 0]} name="AQI Intensity" />
                            <Line type="monotone" dataKey="pm25" stroke="var(--primary-600)" strokeWidth={3} name="PM2.5 Trend" dot={{ r: 4, fill: '#fff', strokeWidth: 2 }} />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="md:col-span-1 flex flex-col gap-4">
                <div className="bg-primary-50 rounded-2xl p-6 shadow-sm border border-primary-100 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary-100/50 flex items-center justify-center text-primary-600">
                        <TrendingUp className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-xs text-primary-500 font-medium uppercase tracking-wide">Model Confidence</p>
                        <p className="text-2xl font-bold text-primary-700">Mesh Active</p>
                    </div>
                </div>


            </div>
        </div>
    );
};

export default ComposedChartHotspots;
