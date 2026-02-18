import { Bell, Shield, User, Globe, Smartphone, Moon } from 'lucide-react';

const SettingsView = () => {
    const settings = [
        { icon: User, label: 'Account Profile', desc: 'Manage your personal information' },
        { icon: Bell, label: 'Notifications', desc: 'Configure alert preferences' },
        { icon: Shield, label: 'Privacy & Security', desc: 'Password and authentication' },
        { icon: Globe, label: 'Language & Region', desc: 'English (US), New York Time' },
        { icon: Moon, label: 'Appearance', desc: 'Light mode active' },
        { icon: Smartphone, label: 'Connected Devices', desc: '5 sensors active' },
    ];

    return (
        <div className="h-full flex flex-col">
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-800 uppercase tracking-wide">
                    Settings
                </h1>
                <h2 className="text-xl text-gray-500">
                    Preferences & Configuration
                </h2>
            </div>

            <div className="grid grid-cols-2 gap-6">
                {settings.map((setting, index) => (
                    <div key={index} className="bg-white p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow cursor-pointer flex items-center gap-4">
                        <div className="w-12 h-12 bg-gray-50 rounded-xl flex items-center justify-center">
                            <setting.icon className="w-6 h-6 text-gray-600" />
                        </div>
                        <div>
                            <h3 className="font-semibold text-gray-800">{setting.label}</h3>
                            <p className="text-sm text-gray-500">{setting.desc}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default SettingsView;
