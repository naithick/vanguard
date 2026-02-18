import { useState, useEffect } from 'react';
import ColumnChartPollutants from '../charts/ColumnChartPollutants';
import LineChartTemperatures from '../charts/LineChartTemperatures';
import PieChartFleet from '../charts/PieChartFleet';
import ComposedChartHotspots from '../charts/ComposedChartHotspots';
import { apiClient } from '../../api/client';
import type { Reading, Stats, DeviceWithReading } from '../../api/client';

interface AnalyticsViewProps {
    searchQuery?: string;
}

const AnalyticsView = ({ searchQuery = '' }: AnalyticsViewProps) => {
    const [readings, setReadings] = useState<Reading[]>([]);
    const [stats, setStats] = useState<Stats | null>(null);
    const [devices, setDevices] = useState<DeviceWithReading[]>([]);

    useEffect(() => {
        const fetchData = async () => {
            const [data, statsData, deviceList] = await Promise.all([
                apiClient.getReadings(100),
                apiClient.getStats(),
                apiClient.getDevices()
            ]);

            if (data) setReadings(data);
            if (statsData) setStats(statsData);
            if (deviceList) setDevices(deviceList);
        };

        fetchData();
        const interval = setInterval(fetchData, 10000);
        return () => clearInterval(interval);
    }, []);

    const allCharts = [
        { id: 'pollutants', title: 'Pollutant Levels', component: <ColumnChartPollutants readings={readings} /> },
        { id: 'fleet', title: 'Fleet Status', component: <PieChartFleet devices={devices} stats={stats} /> },
        { id: 'hotspots', title: 'Predictive Hotspots', component: <ComposedChartHotspots readings={readings} /> },
        { id: 'temp', title: 'Temperatures', component: <LineChartTemperatures readings={readings} /> },
    ];

    const filteredCharts = allCharts.filter(chart =>
        chart.title.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="h-full flex flex-col">
            <div className="mb-6">
                <h1 className="text-2xl font-extrabold text-primary-700 uppercase tracking-tighter">
                    Analytics & Reports
                </h1>
                <h2 className="text-xl text-primary-600 font-medium tracking-tight">
                    Comprehensive Data Overview
                </h2>
            </div>

            <div className={`grid grid-cols-12 gap-6 pb-6 ${filteredCharts.length === 1 ? 'h-full' : ''}`}>
                {filteredCharts.length > 0 ? (
                    filteredCharts.map((chart) => (
                        <div
                            key={chart.id}
                            className={`
                                ${filteredCharts.length === 1 ? 'col-span-12 h-full' : 'col-span-12 lg:col-span-12 h-[500px]'} 
                                transition-all duration-300
                            `}
                        >
                            {chart.component}
                        </div>
                    ))
                ) : (
                    <div className="col-span-12 text-center py-20 text-gray-500">
                        No charts found matching "{searchQuery}"
                    </div>
                )}
            </div>
        </div>
    );
};

export default AnalyticsView;
