import { useState, useEffect } from 'react';
import { Search, Bell, AlertTriangle, ChevronDown, Wifi, WifiOff, User, Settings, LogOut, Camera } from 'lucide-react';
import type { Reading, HealthStatus } from '../api/client';
import { apiClient } from '../api/client';

interface HeaderProps {
  searchQuery?: string;
  setSearchQuery?: (query: string) => void;
  onTabChange?: (tab: string) => void;
  onReportClick?: () => void;
  latestReading?: Reading | null;
}

const Header = ({ searchQuery, setSearchQuery, onTabChange, onReportClick, latestReading }: HeaderProps) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [avatarMenuOpen, setAvatarMenuOpen] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      const h = await apiClient.getHealth();
      setHealth(h);
      setBackendOnline(!!h);
    };
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const chartOptions = [
    'Pollutant Levels',
    'Fleet Status',
    'Wind Status',
    'Predictive Hotspots',
    'Temperatures'
  ];

  const handleOptionSelect = (option: string) => {
    setSearchQuery?.(option);
    setShowDropdown(false);
    onTabChange?.('analytics');
  };

  // Live stats from the latest reading
  const stats = [
    {
      label: 'PM2.5',
      value: latestReading?.pm25_ugm3?.toFixed(1) ?? '--',
      unit: 'µg/m³',
      subValue: latestReading?.aqi_category ?? 'No data'
    },
    {
      label: 'CO₂',
      value: latestReading?.co2_ppm?.toFixed(0) ?? '--',
      unit: 'ppm',
      subValue: latestReading?.co_ppm ? `CO: ${latestReading.co_ppm.toFixed(1)} ppm` : '--'
    },
    {
      label: 'Temp',
      value: latestReading?.temperature_c?.toFixed(1) ?? '--',
      unit: '°C',
      subValue: latestReading?.heat_index_c ? `HI: ${latestReading.heat_index_c.toFixed(1)}°C` : '--'
    },
    {
      label: 'Humidity',
      value: latestReading?.humidity_pct?.toFixed(0) ?? '--',
      unit: '%',
      subValue: latestReading?.pressure_hpa ? `${latestReading.pressure_hpa.toFixed(0)} hPa` : '--'
    },
    {
      label: 'AQI',
      value: latestReading?.aqi_value?.toString() ?? '--',
      unit: '',
      subValue: latestReading?.respiratory_risk_label ?? '--'
    },
  ];

  return (
    <div className="bg-white px-6 py-3 shadow-sm flex items-center justify-between relative z-50">
      {/* Search Bar */}
      <div className="relative">
        <div className="flex items-center bg-primary-50 rounded-full px-4 py-2 w-72 border border-primary-100/50">
          <Search className="w-4 h-4 text-primary-400 mr-2" />
          <input
            type="text"
            placeholder="Search charts..."
            className="bg-transparent outline-none text-sm text-primary-700 w-full placeholder:text-primary-300"
            value={searchQuery}
            onChange={(e) => setSearchQuery?.(e.target.value)}
            onFocus={() => setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
          />
          <ChevronDown
            className={`w-4 h-4 text-primary-400 transition-transform cursor-pointer ${showDropdown ? 'rotate-180' : ''}`}
            onClick={() => setShowDropdown(!showDropdown)}
          />
        </div>

        {/* Dropdown Menu */}
        {showDropdown && (
          <div className="absolute top-full left-0 w-full mt-2 bg-white rounded-xl shadow-lg border border-primary-200 py-2 animate-in fade-in slide-in-from-top-2">
            <div className="px-4 py-2 text-xs font-semibold text-primary-400 uppercase">Analytical Views</div>
            {chartOptions.map((option) => (
              <button
                key={option}
                onClick={() => handleOptionSelect(option)}
                className="w-full text-left px-4 py-2 text-sm text-primary-700 hover:bg-primary-50 hover:text-primary-600 transition-colors flex items-center gap-2"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-primary-400"></div>
                {option} Graph
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Live Stats Bar */}
      <div className="flex items-center gap-8">
        {stats.map((stat, index) => (
          <div key={index} className="text-center">
            <div className="text-xs text-primary-500 font-medium">{stat.label}</div>
            <div className="text-sm font-bold text-primary-800">
              {stat.value}
              {stat.unit && <span className="text-xs text-primary-400 ml-0.5 font-normal">{stat.unit}</span>}
            </div>
            <div className="text-[10px] text-primary-400 font-medium">{stat.subValue}</div>
          </div>
        ))}
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-4">
        {/* Backend Status */}
        <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${backendOnline ? 'bg-status-success/10' : 'bg-status-error/10'
          }`}>
          {backendOnline ? (
            <Wifi className="w-4 h-4 text-status-success" />
          ) : (
            <WifiOff className="w-4 h-4 text-status-error" />
          )}
          <span className={`text-sm font-medium ${backendOnline ? 'text-status-success' : 'text-status-error'
            }`}>
            {backendOnline ? 'API Online' : 'API Offline'}
          </span>
        </div>

        <button
          onClick={() => onTabChange?.('alerts')}
          className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center hover:bg-primary-100 transition-colors text-primary-500"
        >
          <Bell className="w-5 h-5" />
        </button>

        {/* User Avatar with Dropdown */}
        <div className="relative">
          <button
            onClick={() => setAvatarMenuOpen(!avatarMenuOpen)}
            className="w-10 h-10 bg-gradient-to-br from-nature-fern to-nature-teal rounded-full flex items-center justify-center text-white font-semibold shadow-lg shadow-nature-fern/20 hover:scale-105 transition-transform cursor-pointer"
          >
            A
          </button>

          {avatarMenuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setAvatarMenuOpen(false)} />
              <div className="absolute right-0 top-12 w-52 bg-white rounded-xl shadow-xl border border-gray-100 py-2 z-50 animate-in fade-in slide-in-from-top-2">
                <div className="px-4 py-2 border-b border-gray-100 mb-1">
                  <p className="text-sm font-bold text-gray-800">Admin</p>
                  <p className="text-xs text-gray-400">admin@greenroute.io</p>
                </div>
                <button className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-primary-50 hover:text-nature-fern transition-colors">
                  <Camera className="w-4 h-4" />
                  Profile Picture
                </button>
                <button className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-primary-50 hover:text-nature-fern transition-colors">
                  <User className="w-4 h-4" />
                  My Profile
                </button>
                <button onClick={() => { setAvatarMenuOpen(false); onTabChange?.('settings'); }} className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 hover:bg-primary-50 hover:text-nature-fern transition-colors">
                  <Settings className="w-4 h-4" />
                  Settings
                </button>
                <div className="border-t border-gray-100 mt-1 pt-1">
                  <button className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 transition-colors">
                    <LogOut className="w-4 h-4" />
                    Log Out
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Report Button (Now Deep Blue) */}
        <button
          onClick={onReportClick}
          className="bg-nature-fern hover:bg-nature-teal text-white px-4 py-2 rounded-xl text-sm font-bold shadow-lg shadow-nature-fern/20 transition-all active:scale-95 flex items-center gap-2"
        >
          <AlertTriangle className="w-4 h-4" />
          Report
        </button>
      </div>
    </div>
  );
};

export default Header;
