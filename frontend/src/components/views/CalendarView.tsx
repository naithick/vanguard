import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, AlertTriangle, Wind, Thermometer, Factory, Car, PartyPopper, Cloud, Sun, CloudRain, HeartPulse } from 'lucide-react';
import { apiClient } from '../../api/client';

interface DayData {
    day: number;
    aqi: number;
    status: 'Good' | 'Moderate' | 'Unhealthy' | 'Hazardous';
    temp: number;
    humidity: number;
    weather: string;
    primaryPollutant: string;
    pm25: number;
    co: number;
    readingsCount: number;
    event?: { type: 'Festival' | 'Traffic' | 'Industrial'; name: string };
    alert?: string;
}

const CalendarView = () => {
    // State
    const [currentDate, setCurrentDate] = useState(new Date());
    const [calendarData, setCalendarData] = useState<DayData[]>([]);
    const [selectedDate, setSelectedDate] = useState<DayData | null>(null);
    const [loading, setLoading] = useState(false);

    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    const currentMonthName = currentDate.toLocaleString('default', { month: 'long' });
    const currentYear = currentDate.getFullYear();
    const currentMonth = currentDate.getMonth();

    // Fetch Data
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                // Fetch for current month
                const data = await apiClient.getMonthlyHistory(currentYear, currentMonth + 1); // API expects 1-based month

                // Process data into array matching days in month
                const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
                const processedData: DayData[] = Array.from({ length: daysInMonth }, (_, i) => {
                    const dayNum = i + 1;
                    const found = data.find((d: any) => d.day === dayNum);

                    if (found) {
                        return {
                            day: dayNum,
                            aqi: found.aqi,
                            status: found.status as any,
                            temp: found.temp,
                            humidity: found.humidity || 0,
                            weather: found.weather || 'Sunny',
                            primaryPollutant: found.primaryPollutant,
                            pm25: found.avg_pm25 || 0,
                            co: found.avg_co || 0,
                            readingsCount: found.readings_count || 0,
                            event: found.event,
                            alert: found.alert
                        };
                    } else {
                        // Fallback for future/missing dates
                        return {
                            day: dayNum,
                            aqi: 0,
                            status: 'Good',
                            temp: 0,
                            humidity: 0,
                            weather: 'Unknown',
                            primaryPollutant: '-',
                            pm25: 0,
                            co: 0,
                            readingsCount: 0,
                        };
                    }
                });

                setCalendarData(processedData);

                // Select current day if available, else first day
                const today = new Date().getDate();
                const todayData = processedData.find(d => d.day === today);
                setSelectedDate(todayData || processedData[0] || null);

            } catch (err) {
                console.error("Failed to fetch calendar history", err);
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [currentYear, currentMonth]);

    const handlePrevMonth = () => {
        setCurrentDate(new Date(currentYear, currentMonth - 1, 1));
    };

    const handleNextMonth = () => {
        setCurrentDate(new Date(currentYear, currentMonth + 1, 1));
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'Good': return 'bg-nature-light text-nature-fern border-nature-fern/20 hover:bg-nature-light/50';
            case 'Moderate': return 'bg-yellow-50 text-yellow-700 border-yellow-200/20 hover:bg-yellow-50';
            case 'Unhealthy': return 'bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-50';
            case 'Hazardous': return 'bg-red-50 text-red-700 border-red-200 hover:bg-red-50';
            default: return 'bg-gray-50 text-gray-400 border-gray-100 hover:bg-gray-100 opacity-60';
        }
    };

    const getStatusDot = (status: string) => {
        switch (status) {
            case 'Good': return 'bg-nature-fern';
            case 'Moderate': return 'bg-nature-sun';
            case 'Unhealthy': return 'bg-orange-500';
            case 'Hazardous': return 'bg-red-600';
            default: return 'bg-gray-300';
        }
    };

    const getEventIcon = (type?: string) => {
        switch (type) {
            case 'Festival': return <PartyPopper className="w-3 h-3" />;
            case 'Traffic': return <Car className="w-3 h-3" />;
            case 'Industrial': return <Factory className="w-3 h-3" />;
            default: return null;
        }
    };

    const getWeatherIcon = (weather: string, className = "w-4 h-4") => {
        const w = weather.toLowerCase();
        if (w.includes('cloud') || w.includes('overcast')) return <Cloud className={className} />;
        if (w.includes('rain') || w.includes('drizzle')) return <CloudRain className={className} />;
        return <Sun className={className} />;
    };

    const getHealthAdvice = (status: string) => {
        switch (status) {
            case 'Good': return "Air quality is great! Perfect for outdoor activities.";
            case 'Moderate': return "Sensitive individuals should limit prolonged outdoor exertion.";
            case 'Unhealthy': return "Everyone may begin to experience health effects; members of sensitive groups may experience more serious health effects.";
            case 'Hazardous': return "Health warnings of emergency conditions. The entire population is more likely to be affected.";
            default: return "No data available.";
        }
    };

    return (
        <div className="h-full flex flex-col">
            <div className="mb-6 flex justify-between items-end">
                <div>
                    <h1 className="text-2xl font-bold text-gray-800 uppercase tracking-wide">
                        Historical Air Quality
                    </h1>
                    <h2 className="text-xl text-gray-500 font-medium">
                        {currentMonthName} {currentYear} Calendar
                    </h2>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handlePrevMonth}
                        className="p-2 hover:bg-white rounded-lg shadow-sm border border-gray-100 text-gray-600 transition-colors"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <button
                        onClick={handleNextMonth}
                        className="p-2 hover:bg-white rounded-lg shadow-sm border border-gray-100 text-gray-600 transition-colors"
                    >
                        <ChevronRight className="w-5 h-5" />
                    </button>
                </div>
            </div>

            <div className="flex gap-6 h-full min-h-0">
                {/* Main Calendar Grid */}
                <div className="flex-1 bg-white rounded-3xl p-6 shadow-sm flex flex-col overflow-hidden">
                    {/* Days Header */}
                    <div className="grid grid-cols-7 gap-4 mb-4 border-b border-gray-100 pb-4">
                        {days.map(day => (
                            <div key={day} className="text-center text-sm font-semibold text-gray-400 uppercase tracking-wider">
                                {day}
                            </div>
                        ))}
                    </div>

                    {/* Date Grid */}
                    {loading ? (
                        <div className="flex-1 flex items-center justify-center text-gray-400 animate-pulse">
                            Loading history...
                        </div>
                    ) : (
                        <div className="grid grid-cols-7 gap-4 flex-1 overflow-y-auto">
                            {/* Empty slots for start of month padding */}
                            {Array.from({ length: new Date(currentYear, currentMonth, 1).getDay() }).map((_, i) => (
                                <div key={`empty-${i}`} className="rounded-2xl p-3" />
                            ))}
                            {calendarData.map(date => (
                                <div
                                    key={date.day}
                                    onClick={() => setSelectedDate(date)}
                                    className={`
                                        relative rounded-2xl p-3 flex flex-col justify-between cursor-pointer transition-all duration-200 border border-transparent
                                        ${getStatusColor(date.status)}
                                        ${selectedDate?.day === date.day ? 'ring-2 ring-offset-2 ring-nature-fern scale-[0.98]' : 'hover:scale-[1.02] hover:shadow-md'}
                                    `}
                                >
                                    <div className="flex justify-between items-start">
                                        <span className="text-lg font-bold">{date.day}</span>
                                        <div className="flex gap-1">
                                            {date.weather && (
                                                <div className="p-1 bg-white/50 rounded-full" title={date.weather}>
                                                    {getWeatherIcon(date.weather, "w-3 h-3 text-gray-600")}
                                                </div>
                                            )}
                                            {date.event && (
                                                <div className="p-1 bg-white/50 rounded-full" title={date.event.name}>
                                                    {getEventIcon(date.event.type)}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {date.aqi > 0 ? (
                                        <div className="mt-2">
                                            <div className="text-xs font-medium opacity-80">AQI</div>
                                            <div className="text-xl font-bold leading-none">{date.aqi}</div>
                                        </div>
                                    ) : (
                                        <div className="mt-2 text-xs opacity-40">-</div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Daily Details Sidebar */}
                <div className="w-96 bg-white rounded-3xl p-6 shadow-sm flex flex-col border-l border-gray-50 overflow-y-auto">
                    {selectedDate ? (
                        <>
                            <div className="mb-6">
                                <span className="inline-block px-3 py-1 rounded-full text-xs font-bold bg-nature-light text-nature-fern mb-2">
                                    {currentMonthName} {selectedDate.day}, {currentYear}
                                </span>
                                <h3 className="text-2xl font-bold text-gray-800 mb-1">Daily Air Report</h3>
                                <p className="text-gray-500 text-sm">Tambaram Station</p>
                            </div>

                            {/* Score Card */}
                            <div className={`rounded-2xl p-6 mb-6 text-center relative overflow-hidden ${getStatusColor(selectedDate.status).replace('hover:bg-', 'bg-').replace('opacity-60', '')}`}>
                                <div className="relative z-10">
                                    <div className="text-sm font-medium opacity-70 mb-1">Average AQI</div>
                                    <div className="text-5xl font-bold mb-2">{selectedDate.aqi}</div>
                                    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/50 backdrop-blur-sm text-sm font-bold`}>
                                        <div className={`w-2 h-2 rounded-full ${getStatusDot(selectedDate.status)}`}></div>
                                        {selectedDate.status}
                                    </div>
                                </div>
                            </div>

                            {/* Critical Alert */}
                            {selectedDate.alert && (
                                <div className="bg-red-50 border border-red-100 rounded-xl p-4 mb-6 flex items-start gap-3">
                                    <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                                    <div>
                                        <h4 className="text-sm font-bold text-red-600">Health Alert</h4>
                                        <p className="text-xs text-red-500 mt-1">{selectedDate.alert}</p>
                                    </div>
                                </div>
                            )}

                            {/* Metrics Grid */}
                            <div className="grid grid-cols-2 gap-4 mb-6">
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-gray-400 mb-2">
                                        <Thermometer className="w-4 h-4" />
                                        <span className="text-xs font-bold">Avg Temperature</span>
                                    </div>
                                    <div className="text-lg font-bold text-gray-700">{selectedDate.temp}°C</div>
                                </div>
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-gray-400 mb-2">
                                        <Cloud className="w-4 h-4" />
                                        <span className="text-xs font-bold">Avg Humidity</span>
                                    </div>
                                    <div className="text-lg font-bold text-gray-700">{selectedDate.humidity}%</div>
                                </div>
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-gray-400 mb-2">
                                        <Wind className="w-4 h-4" />
                                        <span className="text-xs font-bold">Avg PM2.5</span>
                                    </div>
                                    <div className="text-lg font-bold text-gray-700">{selectedDate.pm25} <span className="text-xs font-normal text-gray-400">µg/m³</span></div>
                                </div>
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-gray-400 mb-2">
                                        <Factory className="w-4 h-4" />
                                        <span className="text-xs font-bold">Avg CO Level</span>
                                    </div>
                                    <div className="text-lg font-bold text-gray-700">{selectedDate.co} <span className="text-xs font-normal text-gray-400">ppm</span></div>
                                </div>
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-gray-400 mb-2">
                                        <CalendarIcon className="w-4 h-4" />
                                        <span className="text-xs font-bold">Total Readings</span>
                                    </div>
                                    <div className="text-lg font-bold text-gray-700">{selectedDate.readingsCount}</div>
                                </div>
                                <div className="bg-gray-50 rounded-xl p-4">
                                    <div className="flex items-center gap-2 text-gray-400 mb-2">
                                        <AlertTriangle className="w-4 h-4" />
                                        <span className="text-xs font-bold">Main Pollutant</span>
                                    </div>
                                    <div className="text-lg font-bold text-gray-700">{selectedDate.primaryPollutant}</div>
                                </div>
                            </div>

                            {/* Health Advice */}
                            <div className="bg-blue-50/50 rounded-2xl p-4 mb-6 border border-blue-100">
                                <div className="flex items-center gap-2 text-blue-700 mb-2 font-bold text-sm">
                                    <HeartPulse className="w-4 h-4" />
                                    Health Recommendation
                                </div>
                                <p className="text-sm text-blue-900/80 leading-relaxed">
                                    {getHealthAdvice(selectedDate.status)}
                                </p>
                            </div>

                            {/* Event Details */}
                            {selectedDate.event && (
                                <div className="border-t border-gray-100 pt-6 mt-auto">
                                    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">City Event Impact</h4>
                                    <div className="flex items-center gap-4 bg-indigo-50 p-4 rounded-xl border border-indigo-100">
                                        <div className="p-2 bg-indigo-100 rounded-lg text-indigo-600">
                                            {getEventIcon(selectedDate.event.type)}
                                        </div>
                                        <div>
                                            <div className="text-sm font-bold text-indigo-900">{selectedDate.event.name}</div>
                                            <div className="text-xs text-indigo-600">Contrib. to +15% AQI spike</div>
                                        </div>
                                    </div>
                                </div>
                            )}

                        </>
                    ) : (
                        <div className="flex items-center justify-center h-full text-gray-400 flex-col">
                            <CalendarIcon className="w-12 h-12 mb-4 opacity-20" />
                            <p>Select a date to view detailed report</p>
                            {loading && <p className="text-xs mt-2 animate-pulse">Updating...</p>}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CalendarView;
