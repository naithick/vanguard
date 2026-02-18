import { useState, useEffect } from 'react';
import { AlertTriangle, AlertCircle, Info, Bell, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { apiClient } from '../api/client';

interface Alert {
    id: string;
    alert_type: string;
    severity: string;
    title: string;
    message: string;
    created_at: string;
    active: boolean;
    device_id?: string;
}

const AIInsightCards = () => {
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [alerts, setAlerts] = useState<Alert[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAlerts = async () => {
            try {
                const data = await apiClient.getAlerts(false, 10); // Get last 10 alerts
                setAlerts(data);
            } catch (err) {
                console.error('Failed to fetch alerts:', err);
            } finally {
                setLoading(false);
            }
        };

        fetchAlerts();
        const interval = setInterval(fetchAlerts, 15000); // Refresh every 15s
        return () => clearInterval(interval);
    }, []);

    const getAlertConfig = (severity: string) => {
        switch (severity) {
            case 'critical':
                return { icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-50', border: 'border-red-100' };
            case 'danger':
                return { icon: AlertTriangle, color: 'text-orange-500', bg: 'bg-orange-50', border: 'border-orange-100' };
            case 'warning':
                return { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-50', border: 'border-amber-100' };
            default:
                return { icon: Info, color: 'text-blue-500', bg: 'bg-blue-50', border: 'border-blue-100' };
        }
    };

    const formatTime = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
        return `${Math.floor(diffMins / 1440)}d ago`;
    };

    const insights = alerts.map(alert => {
        const config = getAlertConfig(alert.severity);
        return {
            id: alert.id,
            category: alert.alert_type.toUpperCase(),
            icon: config.icon,
            color: config.color,
            bg: config.bg,
            border: config.border,
            title: alert.title,
            time: formatTime(alert.created_at),
            summary: alert.message,
            detail: `Device: ${alert.device_id || 'Unknown'} | Status: ${alert.active ? 'Active' : 'Resolved'}`,
            active: alert.active
        };
    });

    const toggleExpand = (id: string) => {
        setExpandedId(expandedId === id ? null : id);
    };

    return (
        <div className="bg-white rounded-2xl p-4 shadow-sm h-full flex flex-col">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-600 flex items-center gap-2">
                    <Bell className="w-4 h-4 text-indigo-500" />
                    Live Alerts
                </h3>
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${alerts.some(a => a.active) ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-500'}`}>
                    {alerts.filter(a => a.active).length} Active
                </span>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                {loading ? (
                    <div className="flex items-center justify-center h-20 text-gray-400 text-xs">
                        Loading alerts...
                    </div>
                ) : insights.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-20 text-gray-400">
                        <Sparkles className="w-6 h-6 mb-2" />
                        <span className="text-xs">No alerts - All systems normal</span>
                    </div>
                ) : (
                    insights.map((item) => (
                        <div
                            key={item.id}
                            onClick={() => toggleExpand(item.id)}
                            className={`rounded-xl p-3 border transition-all duration-200 cursor-pointer hover:shadow-md ${item.bg} ${item.border} ${item.id === expandedId ? 'ring-1 ring-offset-1 ring-gray-200' : ''} ${!item.active ? 'opacity-60' : ''}`}
                        >
                            <div className="flex justify-between items-start mb-1">
                                <div className="flex items-center gap-2">
                                    <div className={`p-1.5 rounded-lg bg-white ${item.color} shadow-sm`}>
                                        <item.icon className="w-3.5 h-3.5" />
                                    </div>
                                    <div>
                                        <h4 className="text-xs font-bold text-gray-800">{item.category}</h4>
                                        <span className="text-[10px] text-gray-500 block -mt-0.5">{item.time}</span>
                                    </div>
                                </div>
                                {item.id === expandedId ? <ChevronUp className="w-3.5 h-3.5 text-gray-400" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-400" />}
                            </div>

                            <h5 className="text-xs font-semibold text-gray-700 mb-1">{item.title}</h5>
                            <p className="text-xs text-gray-600 leading-relaxed">
                                {item.summary}
                            </p>

                            {/* Expandable Content */}
                            {item.id === expandedId && (
                                <div className="mt-2 pt-2 border-t border-gray-200/50">
                                    <p className="text-[11px] text-gray-500 italic bg-white/50 p-2 rounded-lg">
                                        "{item.detail}"
                                    </p>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>

            <style>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: transparent;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background-color: #e5e7eb;
                    border-radius: 20px;
                }
            `}</style>
        </div>
    );
};

export default AIInsightCards;
