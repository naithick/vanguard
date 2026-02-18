import type { Reading } from '../api/client';

interface CitySituationBarProps {
    city: string;
    reading: Reading | null;
}

const getAQILabel = (aqi: number): string => {
    if (aqi <= 50) return 'Good';
    if (aqi <= 100) return 'Moderate';
    if (aqi <= 150) return 'Unhealthy for Sensitive Groups';
    if (aqi <= 200) return 'Unhealthy';
    if (aqi <= 300) return 'Very Unhealthy';
    return 'Hazardous';
};

const getStatusConfig = (category: string) => {
    const lower = category.toLowerCase();
    if (lower === 'good') return { bg: 'bg-primary-50/50', border: 'border-primary-100', text: 'text-primary-700', dot: 'bg-primary-500' };
    if (lower === 'moderate') return { bg: 'bg-primary-200/50', border: 'border-primary-300', text: 'text-primary-800', dot: 'bg-primary-600' };
    return { bg: 'bg-primary-100/80', border: 'border-primary-200', text: 'text-primary-900', dot: 'bg-primary-700' };
};

const CitySituationBar = ({ city, reading }: CitySituationBarProps) => {
    const aqi = reading?.aqi_value ?? 0;
    const status = reading?.aqi_category || getAQILabel(aqi);
    const temp = reading?.temperature_c?.toFixed(1) ?? '--';
    const config = getStatusConfig(status);

    // Construct a dynamic sentence
    const now = new Date();
    const hours = now.getHours();
    const timeOfDay = hours < 12 ? 'Morning' : hours < 17 ? 'Afternoon' : 'Evening';
    const deviceId = reading?.device_id?.substring(0, 8) ?? 'N/A';

    const description = reading
        ? `${timeOfDay} — Device ${deviceId} reports AQI ${aqi} (${status}). Temperature: ${temp}°C. Respiratory risk: ${reading.respiratory_risk_label ?? 'Unknown'}.`
        : `${timeOfDay} — Waiting for sensor data from the network...`;

    return (
        <div className={`${config.bg} ${config.border} border rounded-2xl p-4 mb-6 flex items-center justify-between transition-all duration-300`}>
            <div className="flex items-center gap-3 flex-1">
                <div className={`w-3 h-3 rounded-full ${config.dot} animate-pulse`}></div>
                <div>
                    <span className={`text-sm font-bold ${config.text}`}>{city}</span>
                    <span className="text-sm text-gray-500 ml-2">— {description}</span>
                </div>
            </div>

            <div className="flex items-center gap-4">
                <div className={`px-3 py-1 rounded-full text-xs font-bold ${config.bg} ${config.text} border ${config.border}`}>
                    AQI {aqi}
                </div>
                <div className="text-sm font-semibold text-gray-600">
                    {temp}°C
                </div>
            </div>
        </div>
    );
};

export default CitySituationBar;
