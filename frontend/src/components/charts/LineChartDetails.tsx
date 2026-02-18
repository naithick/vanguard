import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const LineChartDetails = () => {
    const data = [
        { name: 'Mon', temp: 24, humidity: 40 },
        { name: 'Tue', temp: 18, humidity: 30 },
        { name: 'Wed', temp: 28, humidity: 55 },
        { name: 'Thu', temp: 26, humidity: 45 },
        { name: 'Fri', temp: 32, humidity: 60 },
        { name: 'Sat', temp: 22, humidity: 35 },
        { name: 'Sun', temp: 29, humidity: 50 },
    ];

    return (
        <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
            <div className="mb-4">
                <h3 className="text-sm font-semibold text-primary-600">Temperature Trends (Line)</h3>
            </div>
            <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#9ca3af' }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#9ca3af' }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="temp" stroke="var(--primary-600)" strokeWidth={3} dot={{ r: 4 }} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default LineChartDetails;
