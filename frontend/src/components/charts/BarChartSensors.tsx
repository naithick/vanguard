import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const BarChartSensors = () => {
    const data = [
        { name: 'Sensor A', value: 4000 },
        { name: 'Sensor B', value: 3000 },
        { name: 'Sensor C', value: 2000 },
        { name: 'Sensor D', value: 2780 },
        { name: 'Sensor E', value: 1890 },
    ];

    return (
        <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
            <div className="mb-4">
                <h3 className="text-sm font-semibold text-primary-600">Sensor Readings (Bar)</h3>
            </div>
            <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart layout="vertical" data={data}>
                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                        <XAxis type="number" hide />
                        <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 10, fill: '#5F6F62' }} axisLine={false} tickLine={false} />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="value" fill="var(--primary-600)" radius={[0, 4, 4, 0]} barSize={20} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default BarChartSensors;
