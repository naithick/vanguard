import { useState, useEffect } from 'react';
import { Calendar, Download, TrendingDown, TrendingUp, Play, Pause, RefreshCw, Map, Info } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { apiClient } from '../../api/client';

const HistoryView = () => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [sliderValue, setSliderValue] = useState(30);
    const [trendData, setTrendData] = useState<any[]>([]);
    const [analysis, setAnalysis] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    // Mock Data Generator (Frontend Only)
    useEffect(() => {
        // Generate realistic pattern: Morning peak (8-10am), Evening peak (7-9pm)
        const generateMockData = () => {
            const data = [];
            for (let i = 0; i < 24; i++) {
                // Base curve
                let base = 20;

                // Morning Peak
                if (i >= 7 && i <= 10) base += 25 * Math.sin((i - 7) * Math.PI / 3);

                // Evening Peak
                if (i >= 18 && i <= 22) base += 35 * Math.sin((i - 18) * Math.PI / 4);

                // Random variation
                const todayVal = Math.max(10, base + Math.random() * 10);
                const lastWeekVal = Math.max(10, base * 0.8 + Math.random() * 8); // Last week was cleaner

                data.push({
                    time: `${i.toString().padStart(2, '0')}:00`,
                    today: Math.round(todayVal),
                    lastWeek: Math.round(lastWeekVal)
                });
            }
            return data;
        };

        setTrendData(generateMockData());
        setLoading(false);
    }, []);

    // Simulate Replay Animation
    useEffect(() => {
        let interval: NodeJS.Timeout;
        if (isPlaying) {
            interval = setInterval(() => {
                setSliderValue(prev => (prev >= 100 ? 0 : prev + 1));
            }, 50);
        }
        return () => clearInterval(interval);
    }, [isPlaying]);

    return (
        <div className="h-full flex flex-col space-y-6">
            {/* Header & Controls */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-primary-800 uppercase tracking-wide">
                        Historical Analysis
                    </h1>
                    <h2 className="text-xl text-gray-500 font-medium">
                        Comparative Report (PM2.5)
                    </h2>
                </div>
                <div className="flex items-center gap-3">
                    <button className="flex items-center gap-2 bg-white border border-gray-200 text-gray-600 px-4 py-2 rounded-xl hover:bg-gray-50 transition-colors shadow-sm">
                        <Calendar className="w-4 h-4" />
                        <span>Today vs Last Week</span>
                    </button>
                    <button className="flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-xl hover:opacity-90 transition-all shadow-lg shadow-primary-600/20">
                        <Download className="w-4 h-4" />
                        Export
                    </button>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 gap-6">
                <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
                    <div className="text-sm text-gray-500 mb-1">Overall Trend</div>
                    <div className="flex items-end gap-2">
                        {loading ? (
                            <span className="text-xl text-gray-300">...</span>
                        ) : (
                            <>
                                <span className={`text-3xl font-bold text-primary-600`}>
                                    +15%
                                </span>
                                <div className={`flex items-center text-sm font-bold mb-1 text-primary-500`}>
                                    <TrendingUp className="w-4 h-4" />
                                    Worsening
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {/* 
                   Removed AI Insight & Explanation section 
                   as per user request.
                */}
            </div>

            {/* Main Comparison Chart */}
            <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100 flex-1 min-h-[300px]">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="font-bold text-primary-800 flex items-center gap-2">
                        <RefreshCw className="w-4 h-4 text-primary-500" />
                        Trend Comparison
                    </h3>
                    <div className="flex gap-4 text-xs font-bold">
                        <div className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full bg-[#10b981]"></span> Today
                        </div>
                        <div className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full bg-[#ced4da]"></span> Last Week
                        </div>
                    </div>
                </div>

                <div className="h-[250px] w-full">
                    {loading ? (
                        <div className="w-full h-full flex items-center justify-center">
                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                        </div>
                    ) : (
                        <div style={{ width: '100%', height: '100%' }}>
                            {/* Fixed dimensions for debugging */}
                            <AreaChart width={600} height={250} data={trendData}>
                                <defs>
                                    <linearGradient id="colorToday" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f3f4f6" opacity={0.5} />
                                <XAxis
                                    dataKey="time"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                                    interval={2} // Show fewer ticks to be cleaner
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                                    domain={[0, 'auto']}
                                    width={30}
                                />
                                <Tooltip
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="lastWeek"
                                    stroke="#ced4da"
                                    strokeWidth={2}
                                    fill="transparent"
                                    strokeDasharray="5 5"
                                    dot={false}
                                    activeDot={false}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="today"
                                    stroke="#10b981"
                                    strokeWidth={3}
                                    fill="url(#colorToday)"
                                    dot={false}
                                    activeDot={{ r: 4, strokeWidth: 0 }}
                                />
                            </AreaChart>
                        </div>
                    )}
                </div>
            </div>

            {/* Heatmap Replay Slider */}
            <div className="bg-white rounded-3xl p-6 shadow-sm border border-gray-100">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="font-bold text-primary-800 flex items-center gap-2">
                        <Map className="w-4 h-4 text-primary-500" />
                    </h3>
                    <button
                        onClick={() => setIsPlaying(!isPlaying)}
                        className={`p-2 rounded-full transition-all ${isPlaying ? 'bg-primary-100 text-primary-600' : 'bg-primary-50 text-primary-700 hover:bg-primary-100'}`}
                    >
                        {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
                    </button>
                </div>

                <div className="relative h-24 bg-gray-100 rounded-xl overflow-hidden mb-4 group cursor-crosshair">
                    {/* Abstract Heatmap Visual - Blue/Cool Theme */}
                    <div className="absolute inset-0 opacity-50 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-blue-300 via-indigo-100 to-transparent"></div>
                    <div className="absolute inset-0 opacity-30 bg-[radial-gradient(ellipse_at_bottom_right,_var(--tw-gradient-stops))] from-sky-300 via-blue-50 to-transparent"></div>

                    {/* Time Indicator Line */}
                    <div
                        className="absolute top-0 bottom-0 w-0.5 bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.5)] z-10"
                        style={{ left: `${sliderValue}%` }}
                    >
                        <div className="absolute -top-1 -translate-x-1/2 bg-indigo-600 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-sm">
                            {Math.floor((sliderValue / 100) * 24)}:00
                        </div>
                    </div>

                    {/* Animated Blobs based on slider */}
                    <div
                        className="absolute transition-all duration-300 ease-out blur-xl rounded-full bg-red-500/40 w-32 h-32"
                        style={{
                            top: '20%',
                            left: `${20 + (Math.sin(sliderValue / 10) * 10)}%`,
                            opacity: (sliderValue > 30 && sliderValue < 70) ? 0.8 : 0.2
                        }}
                    />
                    <div
                        className="absolute transition-all duration-300 ease-out blur-xl rounded-full bg-orange-500/40 w-24 h-24"
                        style={{
                            top: '50%',
                            left: `${60 - (Math.sin(sliderValue / 20) * 10)}%`,
                            opacity: (sliderValue > 60) ? 0.8 : 0.3
                        }}
                    />
                </div>

                <input
                    type="range"
                    min="0"
                    max="100"
                    value={sliderValue}
                    onChange={(e) => {
                        setSliderValue(Number(e.target.value));
                        setIsPlaying(false);
                    }}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-2 font-medium">
                    <span>00:00</span>
                    <span>06:00</span>
                    <span>12:00</span>
                    <span>18:00</span>
                    <span>23:59</span>
                </div>
            </div>
        </div>
    );
};

export default HistoryView;
