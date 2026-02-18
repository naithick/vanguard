import { useState } from 'react';
import { HeartPulse, Car, CloudRain, Factory, Leaf, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

const AIInsightCards = () => {
    const [expandedId, setExpandedId] = useState<number | null>(null);

    const insights = [
        {
            id: 1,
            category: 'Health',
            icon: HeartPulse,
            color: 'text-rose-500',
            bg: 'bg-rose-50',
            border: 'border-rose-100',
            title: 'Respiratory Alert',
            time: 'Just now',
            summary: 'High PM2.5 levels in Sector 7 may affect sensitive groups.',
            detail: 'AI analysis suggests wearing masks for outdoor activities. Hospitals in the area are on standby for respiratory cases.'
        },
        {
            id: 2,
            category: 'Traffic',
            icon: Car,
            color: 'text-amber-500',
            bg: 'bg-amber-50',
            border: 'border-amber-100',
            title: 'Congestion Easing',
            time: '5m ago',
            summary: 'Traffic flow improving on Main Street corridor.',
            detail: 'Smart signals have adjusted timing to clear the backlog. Expect normal flow within 15 minutes.'
        },
        {
            id: 3,
            category: 'Weather',
            icon: CloudRain,
            color: 'text-sky-500',
            bg: 'bg-sky-50',
            border: 'border-sky-100',
            title: 'Rain Approaching',
            time: '12m ago',
            summary: 'Light showers expected in the northern districts.',
            detail: 'Precipitation will likely help reduce suspended particulate matter (PM10) by 15% over the next hour.'
        },
        {
            id: 4,
            category: 'Industry',
            icon: Factory,
            color: 'text-purple-500',
            bg: 'bg-purple-50',
            border: 'border-purple-100',
            title: 'Emission Spike',
            time: '25m ago',
            summary: 'Unusual SO2 activity detected near Industrial Zone B.',
            detail: 'Automated sensors have flagged this anomaly. Authorities have been notifying the plant manager for inspection.'
        },
        {
            id: 5,
            category: 'Environment',
            icon: Leaf,
            color: 'text-emerald-500',
            bg: 'bg-emerald-50',
            border: 'border-emerald-100',
            title: 'Ozone Normal',
            time: '1h ago',
            summary: 'Ground-level ozone levels have stabilized.',
            detail: 'Good news! The earlier spike has dissipated due to increased cloud cover and reduced UV radiation.'
        }
    ];

    const toggleExpand = (id: number) => {
        setExpandedId(expandedId === id ? null : id);
    };

    return (
        <div className="bg-white rounded-2xl p-4 shadow-sm h-full flex flex-col">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-gray-600 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-indigo-500" />
                    AI Insights Feed
                </h3>
                <span className="text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Live</span>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
                {insights.map((item) => (
                    <div
                        key={item.id}
                        onClick={() => toggleExpand(item.id)}
                        className={`rounded-xl p-3 border transition-all duration-200 cursor-pointer hover:shadow-md ${item.bg} ${item.border} ${item.id === expandedId ? 'ring-1 ring-offset-1 ring-gray-200' : ''}`}
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
                ))}
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
