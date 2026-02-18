import { useState, useEffect } from 'react';
import { apiClient } from '../../api/client';
import type { Reading, Stats, DeviceWithReading } from '../../api/client';

import CityHealthIndex from '../CityHealthIndex';
import WeatherCard from '../WeatherCard';
import SensorDetails from '../SensorDetails';

import TemperatureReports from '../TemperatureReports';
import PollutantLevels from '../PollutantLevels';
import FleetStatus from '../FleetStatus';
import WeatherDetails from '../WeatherDetails';
import SystemStatus from '../SystemStatus';
import CitySituationBar from '../CitySituationBar';
import AirQualityMap from '../AirQualityMap';
import AIInsightCards from '../AIInsightCards';
import PredictiveHotspots from '../PredictiveHotspots';

interface DashboardViewProps {
    selectedCity: string;
    setSelectedCity: (city: string) => void;
    userReports?: any[];
}

const DashboardView = ({ selectedCity, setSelectedCity }: DashboardViewProps) => {
    const [readings, setReadings] = useState<Reading[]>([]);
    const [latestReading, setLatestReading] = useState<Reading | null>(null);
    const [stats, setStats] = useState<Stats | null>(null);
    const [devices, setDevices] = useState<DeviceWithReading[]>([]);
    const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);

    useEffect(() => {
        const fetchData = async () => {
            // Fetch devices
            const deviceList = await apiClient.getDevices();
            setDevices(deviceList);

            // Auto-select first device if none selected
            if (!selectedDeviceId && deviceList.length > 0) {
                setSelectedDeviceId(deviceList[0].device.device_id);
            }

            // Fetch readings (optionally filtered by device)
            const data = await apiClient.getReadings(100, selectedDeviceId ?? undefined);
            if (data.length > 0) {
                setReadings(data);
                setLatestReading(data[0]);
            }

            // Fetch stats
            const statsData = await apiClient.getStats();
            if (statsData) setStats(statsData);
        };

        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, [selectedDeviceId]);

    const selectedDevice = devices.find(d => d.device.device_id === selectedDeviceId);
    const deviceName = selectedDevice?.device.name ?? selectedCity;

    return (
        <div className="space-y-6">
            {/* Title Section */}
            <div className="mb-6">
                <h1 className="text-2xl font-extrabold text-primary-700 uppercase tracking-tighter">
                    Urban Air Intelligence
                </h1>
                <h2 className="text-xl text-primary-600 font-medium tracking-tight">
                    & Prediction System
                </h2>
            </div>

            {/* City Situation Bar */}
            <CitySituationBar city={deviceName} reading={latestReading} />

            {/* Top Grid: Main Metrics & Spatial Map */}
            <div className="grid grid-cols-12 gap-6 h-[450px]">
                {/* Weather & Device Card */}
                <div className="col-span-12 lg:col-span-4 h-full">
                    <WeatherCard
                        selectedCity={selectedCity}
                        onCityChange={setSelectedCity}
                        reading={latestReading}
                        devices={devices}
                        selectedDeviceId={selectedDeviceId}
                        onDeviceChange={setSelectedDeviceId}
                    />
                </div>

                {/* Main Interactive Map */}
                <div className="col-span-12 lg:col-span-8 h-full">
                    <AirQualityMap
                        devices={devices}
                        readings={readings}
                        selectedDeviceID={selectedDeviceId}
                    />
                </div>
            </div>

            {/* Middle Grid: Detailed Environmental Analysis */}
            <div className="grid grid-cols-12 gap-6">
                {/* AQI Gauge */}
                <div className="col-span-12 md:col-span-4">
                    <CityHealthIndex reading={latestReading} device={selectedDevice?.device} />
                </div>

                {/* Pollutant Trends */}
                <div className="col-span-12 md:col-span-4">
                    <PollutantLevels readings={readings} />
                </div>

                {/* Sensor Details */}
                <div className="col-span-12 md:col-span-4">
                    <SensorDetails reading={latestReading} />
                </div>
            </div>

            {/* Bottom Grid: System & Fleet Context */}
            <div className="grid grid-cols-12 gap-6">
                {/* Weather Extras */}
                <div className="col-span-12 md:col-span-4">
                    <WeatherDetails reading={latestReading} />
                </div>

                {/* Fleet Health */}
                <div className="col-span-12 md:col-span-4">
                    <FleetStatus devices={devices} stats={stats} />
                </div>

                {/* System Pipeline */}
                <div className="col-span-12 md:col-span-4">
                    <SystemStatus stats={stats} />
                </div>
            </div>

            {/* Alerts & Hotspots Row */}
            <div className="grid grid-cols-12 gap-6">
                {/* Live Alerts Feed */}
                <div className="col-span-12 md:col-span-6 lg:col-span-4">
                    <AIInsightCards />
                </div>

                {/* Active Hotspots */}
                <div className="col-span-12 md:col-span-6 lg:col-span-4">
                    <PredictiveHotspots />
                </div>

                {/* Mesh Health Reports */}
                <div className="col-span-12 lg:col-span-4">
                    <TemperatureReports reading={latestReading} />
                </div>
            </div>
        </div>
    );
};

export default DashboardView;
