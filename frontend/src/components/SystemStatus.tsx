import { RefreshCw, Layout, Server, Bell, FileText, Flame } from 'lucide-react';
import { apiClient } from '../api/client';
import type { Stats } from '../api/client';
import { useState, useEffect } from 'react';

interface SystemStatusProps {
    stats: Stats | null;
}

const SystemStatus = ({ stats }: SystemStatusProps) => {
    const [isOnline, setIsOnline] = useState(false);
    const [lastSync, setLastSync] = useState<string>('Just now');

    useEffect(() => {
        const checkHealth = async () => {
            const health = await apiClient.getHealth();
            setIsOnline(health !== null);
        };
        checkHealth();
        const interval = setInterval(checkHealth, 15000);
        return () => clearInterval(interval);
    }, []);

    // Update "Last Sync" based on backend data
    useEffect(() => {
        if (stats?.last_data_at) {
            setLastSync(new Date(stats.last_data_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
        } else {
            // Fallback to local time if no stats
            setLastSync(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
        }
    }, [stats]);

    const metrics = [
        {
            label: 'Readings Stored',
            value: stats?.total_readings?.toLocaleString() ?? '—',
            icon: Layout,
        },
        {
            label: 'Avg AQI (Recent)',
            value: stats?.avg_aqi_recent?.toFixed(1) ?? '—',
            icon: Server,
        },
        {
            label: 'Active Alerts',
            value: stats?.active_alert_count?.toString() ?? '—',
            icon: Bell,
        },
        {
            label: 'Open Reports',
            value: stats?.open_report_count?.toString() ?? '—',
            icon: FileText,
        },
        {
            label: 'Active Hotspots',
            value: stats?.active_hotspot_count?.toString() ?? '—',
            icon: Flame,
        },
    ];

    return (
        <div className="bg-white rounded-2xl p-5 shadow-sm h-full">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold text-gray-700">System Pipeline</h3>
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-tighter">Sync: {lastSync}</span>
                    <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-status-success animate-pulse' : 'bg-status-error'}`}></div>
                </div>
            </div>

            <div className="space-y-4">
                {metrics.map((metric, index) => (
                    <div key={index} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <metric.icon className="w-4 h-4 text-gray-400" />
                            <span className="text-xs text-gray-500">{metric.label}</span>
                        </div>
                        <span className="text-sm font-black text-gray-800">{metric.value}</span>
                    </div>
                ))}
            </div>

            <button className="w-full mt-4 bg-primary-50 hover:bg-primary-600 text-primary-600 hover:text-white py-2 rounded-xl text-[10px] font-bold uppercase tracking-widest transition-all border border-primary-600/10 hover:border-transparent shadow-sm flex items-center justify-center gap-2">
                <RefreshCw className="w-3 h-3" />
                Force Re-Sync
            </button>
        </div>
    );
};

export default SystemStatus;
