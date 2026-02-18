import { useState, useEffect } from 'react';
import { MessageSquare, ThumbsUp, MapPin, Clock, Filter, AlertCircle } from 'lucide-react';
import { apiClient } from '../../api/client';

interface Report {
    id: string;
    title: string;
    description: string;
    category: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    status: 'open' | 'investigating' | 'resolved';
    created_at: string;
    upvotes: number;
    reporter_name?: string;
}

const ReportsView = () => {
    const [reports, setReports] = useState<Report[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState<string>('all');

    const fetchReports = async () => {
        setLoading(true);
        try {
            const status = statusFilter === 'all' ? undefined : statusFilter;
            const data = await apiClient.getReports(50, status);
            setReports(data);
        } catch (err) {
            console.error("Failed to fetch reports", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReports();
        const interval = setInterval(fetchReports, 10000);
        return () => clearInterval(interval);
    }, [statusFilter]);

    const handleUpvote = async (id: string) => {
        // Optimistic update
        setReports(prev => prev.map(r => r.id === id ? { ...r, upvotes: (r.upvotes || 0) + 1 } : r));
        try {
            await fetch(`http://localhost:5002/api/reports/${id}/upvote`, { method: 'POST' });
        } catch (e) {
            // Revert if failed (omitted for brevity)
        }
    };

    const getStatusBadge = (status: string) => {
        const styles = {
            open: 'bg-blue-100 text-blue-700 border-blue-200',
            investigating: 'bg-purple-100 text-purple-700 border-purple-200',
            resolved: 'bg-green-100 text-green-700 border-green-200'
        };
        return (
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${styles[status as keyof typeof styles] || styles.open}`}>
                {status}
            </span>
        );
    };

    return (
        <div className="h-full flex flex-col">
            <div className="mb-6 flex justify-between items-end">
                <div>
                    <h1 className="text-2xl font-extrabold text-primary-700 uppercase tracking-tighter">
                        Citizen Reports
                    </h1>
                    <h2 className="text-xl text-primary-600 font-medium tracking-tight">
                        Community Observations
                    </h2>
                </div>

                <div className="flex gap-2">
                    <select
                        className="bg-white border border-gray-200 text-sm rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-primary-500"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="all">All Statuses</option>
                        <option value="open">Open</option>
                        <option value="investigating">Investigating</option>
                        <option value="resolved">Resolved</option>
                    </select>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto pr-2">
                {loading && reports.length === 0 ? (
                    <div className="flex justify-center py-20">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                    </div>
                ) : reports.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-[400px] text-gray-400">
                        <MessageSquare className="w-16 h-16 mb-4 opacity-20" />
                        <p className="text-lg font-medium">No reports found</p>
                        <p className="text-sm">Be the first to report an issue!</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {reports.map((report) => (
                            <div key={report.id} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm hover:shadow-md transition-shadow flex flex-col gap-3">
                                <div className="flex justify-between items-start">
                                    <div className="flex items-center gap-2">
                                        <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded-md text-xs font-semibold">
                                            {report.category}
                                        </span>
                                        {getStatusBadge(report.status)}
                                    </div>
                                    <span className="text-xs text-gray-400 flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {new Date(report.created_at).toLocaleDateString()}
                                    </span>
                                </div>

                                <div>
                                    <h3 className="font-bold text-gray-800 text-lg leading-tight mb-1">{report.title}</h3>
                                    <p className="text-gray-600 text-sm line-clamp-2">{report.description}</p>
                                </div>

                                <div className="mt-auto pt-3 border-t border-gray-50 flex justify-between items-center text-xs text-gray-500">
                                    <div className="flex items-center gap-4">
                                        <span className="flex items-center gap-1">
                                            <MapPin className="w-3 h-3" /> Area Report
                                        </span>
                                        {report.reporter_name && (
                                            <span>by {report.reporter_name}</span>
                                        )}
                                    </div>
                                    <button
                                        onClick={() => handleUpvote(report.id)}
                                        className="flex items-center gap-1.5 bg-gray-50 hover:bg-primary-50 hover:text-primary-600 px-2 py-1 rounded-full transition-colors font-medium border border-gray-200"
                                    >
                                        <ThumbsUp className="w-3 h-3" />
                                        {report.upvotes || 0}
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ReportsView;
