import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Activity, DollarSign } from 'lucide-react';
import type { DeviceWithReading, Stats } from '../../api/client';

interface PieChartFleetProps {
    devices?: DeviceWithReading[];
    stats?: Stats | null;
}

const PieChartFleet = ({ devices = [], stats }: PieChartFleetProps) => {
    const totalDevices = stats?.device_count ?? devices.length;
    const activeDevices = devices.filter(d => d.latest_reading !== null).length;
    const inactiveDevices = totalDevices - activeDevices;

    const data = [
        { name: 'Active Nodes', value: activeDevices },
        { name: 'Offline Nodes', value: inactiveDevices },
    ];

    const COLORS = [
        'var(--chart-1)',
        'var(--chart-2)',
        'var(--chart-3)',
        'var(--chart-4)',
        'var(--chart-5)'
    ];

    const efficiency = totalDevices > 0 ? Math.round((activeDevices / totalDevices) * 100) : 0;

    // Estimate CO2 avoided based on active nodes (just for visual logic)
    const co2Avoided = (activeDevices * 0.45).toFixed(2);

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-white rounded-3xl p-6 shadow-sm border border-gray-100 h-full">
            {/* Left Column: Chart */}
            <div className="md:col-span-2 flex flex-col h-full">
                <h3 className="text-lg font-bold text-primary-700 mb-6 flex items-center gap-2">
                    Fleet Deployment Status
                </h3>
                <div className="flex-1 min-h-[250px] relative">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                paddingAngle={5}
                                dataKey="value"
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip />
                            <Legend iconType="circle" wrapperStyle={{ bottom: 0 }} />
                        </PieChart>
                    </ResponsiveContainer>
                    {/* Center Text */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none flex-col pb-6">
                        <span className="text-3xl font-bold text-primary-700">{efficiency}%</span>
                        <span className="text-xs text-primary-500 font-medium uppercase">Active</span>
                    </div>
                </div>
            </div>

            {/* Right Column: Insights */}
            <div className="md:col-span-1 flex flex-col gap-4">
                <div className="bg-primary-50 rounded-2xl p-6 shadow-sm border border-primary-100 flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-primary-100/50 flex items-center justify-center text-primary-600">
                        <DollarSign className="w-5 h-5" />
                    </div>
                    <div>
                        <p className="text-xs text-primary-500 font-medium uppercase tracking-wide">Network Nodes</p>
                        <p className="text-2xl font-bold text-primary-700">{activeDevices}/{totalDevices}</p>
                    </div>
                </div>

                <div className="bg-primary-50/50 rounded-2xl p-6 border border-primary-100 flex-1 flex flex-col justify-center">
                    <div className="flex items-center gap-2 mb-2 text-primary-700 font-bold text-sm">
                        <Activity className="w-4 h-4" />
                        Network Impact
                    </div>
                    <p className="text-sm text-primary-800 leading-relaxed">
                        There are <span className="font-bold">{activeDevices} sensor nodes</span> contributing to the real-time mesh. This provides a data density of <span className="font-bold">{co2Avoided} kg</span> coverage/sec.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default PieChartFleet;
