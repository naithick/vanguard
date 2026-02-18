import { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, Info, XCircle, Filter } from 'lucide-react';
import { apiClient } from '../../api/client';

interface Alert {
    id: string;
    title: string;
    message: string;
    severity: 'critical' | 'warning' | 'info' | 'danger';
    alert_type: string;
    created_at: string;
    active: boolean;
    device_id: string;
}

const AlertsView = () => {
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('active');

    const fetchAlerts = async () => {
        setLoading(true);
        try {
            // Fetch all to toggle locally or fetch based on filter from API?
            // API supports active=true/false. simpler to fetch based on filter if 'all' is not supported directly without pagination logic complexity
            // Actually API getAlerts(activeOnly)
            const data = await apiClient.getAlerts(filter === 'active');
            // If filter is 'resolved', we might need to fetch active=false? 
            // api/client.ts: getAlerts(activeOnly = true)
            // If I want 'all' or 'resolved', I might need to adjust client or just fetch active=false for resolved.
            // Let's assume for now we toggle: 
            // if filter == active -> getAlerts(true)
            // if filter == resolved -> getAlerts(false) (which might return all inactive?)
            // Wait, getAlerts implementation: `active=${activeOnly}`. If activeOnly is false, it returns ALL or just inactive? 
            // Checking app.py: `if active_only: query = query.eq("active", True)`. So if active_only is false, it returns ALL.

            const isActiveOnly = filter === 'active';
            const res = await apiClient.getAlerts(isActiveOnly);

            // If filtering for 'resolved' specifically, we might need to filter client side from 'all'
            let filtered = res;
            if (filter === 'resolved') {
                // Fetch all (active=false in API param means "don't filter by active", so it returns ALL)
                const all = await apiClient.getAlerts(false);
                filtered = all.filter((a: any) => !a.active);
            } else if (filter === 'all') {
                filtered = await apiClient.getAlerts(false);
            }

            setAlerts(filtered);
        } catch (err) {
            console.error("Failed to fetch alerts", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAlerts();
        const interval = setInterval(fetchAlerts, 10000);
        return () => clearInterval(interval);
    }, [filter]);

    const getSeverityColor = (severity: string) => {
        switch (severity) {
            case 'critical': return 'bg-red-600 border-red-800 text-white shadow-md shadow-red-600/30';
            case 'danger': return 'bg-red-600 border-red-800 text-white shadow-md shadow-red-600/30';
            case 'warning': return 'bg-amber-400 border-amber-600 text-gray-900 shadow-md shadow-amber-400/30';
            default: return 'bg-blue-600 border-blue-800 text-white shadow-md shadow-blue-600/30';
        }
    };

    const getIcon = (severity: string) => {
        switch (severity) {
            case 'critical':
            case 'danger': return <XCircle className="w-5 h-5 text-red-900" />;
            case 'warning': return <AlertTriangle className="w-5 h-5 text-amber-900" />;
            default: return <Info className="w-5 h-5 text-teal-900" />;
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="mb-6 flex justify-between items-end">
                <div>
                    <h1 className="text-2xl font-extrabold text-primary-700 uppercase tracking-tighter">
                        System Alerts
                    </h1>
                    <h2 className="text-xl text-primary-600 font-medium tracking-tight">
                        Real-time Anomalies & Warnings
                    </h2>
                </div>

                {/* Filter Tabs */}
                <div className="flex bg-primary-800/60 p-1 rounded-lg border border-primary-700/50 backdrop-blur-sm">
                    {(['active', 'resolved', 'all'] as const).map((f) => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-4 py-2 rounded-md text-sm font-bold transition-all ${filter === f
                                ? 'bg-primary-600 text-white shadow-md shadow-primary-900/20 border border-primary-500/50'
                                : 'text-primary-300 hover:text-white hover:bg-primary-700/50'
                                }`}
                        >
                            {f.charAt(0).toUpperCase() + f.slice(1)}
                        </button>
                    ))}
                </div>
            </div>

            <div className="flex-1 overflow-y-auto pr-2">
                {loading && alerts.length === 0 ? (
                    <div className="flex justify-center py-20">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                    </div>
                ) : alerts.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-[400px] text-gray-400">
                        <CheckCircle className="w-16 h-16 mb-4 opacity-20" />
                        <p className="text-lg font-medium">No alerts found</p>
                        <p className="text-sm">System is running normally</p>
                    </div>
                ) : (
                    <div className="grid gap-4">
                        {alerts.map((alert) => (
                            <div
                                key={alert.id}
                                className={`p-4 rounded-xl border flex items-start gap-4 transition-all hover:shadow-md ${getSeverityColor(alert.severity)} ${!alert.active ? 'opacity-75 grayscale-[0.5]' : ''}`}
                            >
                                <div className="mt-1 flex-shrink-0">
                                    {getIcon(alert.severity)}
                                </div>
                                <div className="flex-1">
                                    <div className="flex justify-between items-start">
                                        <h3 className="font-bold text-lg">{alert.title}</h3>
                                        <span className="text-xs font-mono opacity-70">
                                            {new Date(alert.created_at).toLocaleString()}
                                        </span>
                                    </div>
                                    <p className="mt-1 text-sm opacity-90">{alert.message}</p>
                                    <div className="mt-3 flex gap-3 text-xs font-semibold uppercase tracking-wider opacity-60">
                                        <span>Device: {alert.device_id}</span>
                                        <span>Type: {alert.alert_type}</span>
                                        {!alert.active && <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Resolved</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AlertsView;
