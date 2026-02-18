import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import DashboardView from './components/views/DashboardView';
import AnalyticsView from './components/views/AnalyticsView';
import HistoryView from './components/views/HistoryView';
import CalendarView from './components/views/CalendarView';
import AlertsView from './components/views/AlertsView';
import ReportsView from './components/views/ReportsView';
import SettingsView from './components/views/SettingsView';
import MapView from './components/views/MapView';
import PollutionReportForm from './components/PollutionReportForm';
import { apiClient } from './api/client';
import type { Reading } from './api/client';
import './App.css';

function App() {
  const [selectedCity, setSelectedCity] = useState('Tambaram');
  const [activeTab, setActiveTab] = useState('home');
  const [searchQuery, setSearchQuery] = useState('');
  const [latestReading, setLatestReading] = useState<Reading | null>(null);

  const handleSidebarTabChange = (tab: string) => {
    setActiveTab(tab);
    setSearchQuery('');
  };

  /* Report Modal State */
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [userReports, setUserReports] = useState<any[]>([]);

  const handleReportSubmit = (report: any) => {
    setUserReports([...userReports, report]);
    console.log("Report Submitted:", report);
  };

  // Fetch latest reading for the header stats bar
  useEffect(() => {
    const fetchLatest = async () => {
      const data = await apiClient.getReadings(1);
      if (data.length > 0) {
        setLatestReading(data[0]);
      }
    };
    fetchLatest();
    const interval = setInterval(fetchLatest, 5000);
    return () => clearInterval(interval);
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <DashboardView selectedCity={selectedCity} setSelectedCity={setSelectedCity} userReports={userReports} />;
      case 'map':
        return <MapView />;
      case 'analytics':
        return <AnalyticsView searchQuery={searchQuery} />;
      case 'history':
        return <HistoryView />;
      case 'calendar':
        return <CalendarView />;
      case 'alerts':
        return <AlertsView />;
      case 'reports':
        return <ReportsView />;
      case 'settings':
        return <SettingsView />;
      default:
        return <DashboardView selectedCity={selectedCity} setSelectedCity={setSelectedCity} userReports={userReports} />;
    }
  };

  return (
    <div className="flex h-screen bg-background overflow-hidden relative">
      {/* Report Form Modal */}
      {isReportModalOpen && (
        <PollutionReportForm
          onClose={() => setIsReportModalOpen(false)}
          onSubmit={handleReportSubmit}
        />
      )}

      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onTabChange={handleSidebarTabChange} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header with live data */}
        <Header
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onTabChange={setActiveTab}
          onReportClick={() => setIsReportModalOpen(true)}
          latestReading={latestReading}
        />

        {/* Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {renderContent()}
        </div>
      </div>
    </div>
  );
}

export default App;
