import { Home, Clock, Calendar, Settings, Activity, BarChart2, Map, MessageSquare } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const Sidebar = ({ activeTab, onTabChange }: SidebarProps) => {
  const menuItems = [
    { id: 'home', icon: Home },
    { id: 'map', icon: Map },
    { id: 'analytics', icon: BarChart2 },
    { id: 'history', icon: Clock },
    { id: 'calendar', icon: Calendar },
    { id: 'reports', icon: MessageSquare },
    { id: 'settings', icon: Settings },
  ];

  return (
    <div className="w-16 bg-white flex flex-col items-center py-4 shadow-sm z-50">
      {/* Logo */}
      <div className="w-10 h-10 bg-gradient-to-br from-nature-fern to-nature-teal rounded-xl flex items-center justify-center mb-8 shadow-lg shadow-nature-fern/20">
        <Activity className="w-6 h-6 text-white" />
      </div>

      {/* Menu Items */}
      <div className="flex flex-col gap-4">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 ${activeTab === item.id
              ? 'bg-nature-fern text-white shadow-md shadow-nature-fern/30'
              : 'text-primary-500 hover:text-nature-fern hover:bg-nature-light'
              }`}
          >
            <item.icon className="w-5 h-5" />
          </button>
        ))}
      </div>
    </div>
  );
};

export default Sidebar;
