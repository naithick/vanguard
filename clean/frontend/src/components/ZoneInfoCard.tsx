import { Shield, AlertTriangle, Info } from 'lucide-react';

interface ZoneInfo {
    id: string;
    name: string;
    type: 'Residential' | 'Industrial' | 'School' | 'Traffic' | 'Hospital';
    aqi: number;
    risk: 'Low' | 'Moderate' | 'High' | 'Critical';
    recommendation: string;
}

const ZoneInfoCard = ({ zone }: { zone: ZoneInfo }) => {
    const getRiskStyles = (risk: string) => {
        switch (risk) {
            case 'Low':
                return {
                    container: 'bg-emerald-50/50 hover:bg-emerald-50 border-emerald-100',
                    badge: 'bg-emerald-100 text-emerald-700',
                    title: 'text-emerald-900'
                };
            case 'Moderate':
                return {
                    container: 'bg-yellow-50/50 hover:bg-yellow-50 border-yellow-100',
                    badge: 'bg-yellow-100 text-yellow-700',
                    title: 'text-yellow-900'
                };
            case 'High':
                return {
                    container: 'bg-orange-50/50 hover:bg-orange-50 border-orange-100',
                    badge: 'bg-orange-100 text-orange-700',
                    title: 'text-orange-900'
                };
            case 'Critical':
                return {
                    container: 'bg-rose-50/50 hover:bg-rose-50 border-rose-100',
                    badge: 'bg-rose-100 text-rose-700',
                    title: 'text-rose-900'
                };
            default:
                return {
                    container: 'bg-gray-50/50 hover:bg-gray-50 border-gray-100',
                    badge: 'bg-gray-100 text-gray-700',
                    title: 'text-gray-900'
                };
        }
    };

    const styles = getRiskStyles(zone.risk);

    return (
        <div className={`rounded-2xl p-5 border shadow-sm transition-all duration-200 ${styles.container}`}>
            <div className="flex justify-between items-start mb-3">
                <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider opacity-60 block mb-1">{zone.type}</span>
                    <h3 className={`font-bold text-lg leading-tight ${styles.title}`}>{zone.name}</h3>
                </div>
                <div className={`px-2.5 py-1 rounded-md text-[10px] font-bold uppercase tracking-wide ${styles.badge}`}>
                    AQI {zone.aqi}
                </div>
            </div>

            <div className="flex items-start gap-2.5">
                <Info className="w-3.5 h-3.5 mt-0.5 opacity-40 shrink-0" />
                <p className="text-sm text-gray-600 leading-relaxed font-medium">
                    {zone.recommendation}
                </p>
            </div>
        </div>
    );
};

export default ZoneInfoCard;
