import { ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const ComposedChartAnalytics = () => {
    const data = [
        { name: 'Jan', toxicity: 590, traffic: 800 },
        { name: 'Feb', toxicity: 868, traffic: 967 },
        { name: 'Mar', toxicity: 1397, traffic: 1098 },
        { name: 'Apr', toxicity: 1480, traffic: 1200 },
        { name: 'May', toxicity: 1520, traffic: 1108 },
        { name: 'Jun', toxicity: 1400, traffic: 680 },
    ];

    return (
        <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
            <div className="mb-4">
                <h3 className="text-sm font-semibold text-primary-600">Environmental Impact (Column + Line)</h3>
            </div>
            <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data}>
                        <CartesianGrid stroke="#f5f5f5" vertical={false} />
                        <XAxis dataKey="name" scale="band" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#6b7280' }} />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="toxicity" barSize={20} fill="var(--primary-600)" radius={[4, 4, 0, 0]} />
                        <Line type="monotone" dataKey="traffic" stroke="var(--primary-400)" strokeWidth={2} />
                    </ComposedChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default ComposedChartAnalytics;
