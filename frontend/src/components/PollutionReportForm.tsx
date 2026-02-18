import { useState } from 'react';
import { X, Camera, MapPin, AlertTriangle, Send } from 'lucide-react';

interface PollutionReportFormProps {
    onClose: () => void;
    onSubmit: (report: any) => void;
}

const PollutionReportForm = ({ onClose, onSubmit }: PollutionReportFormProps) => {
    const [pollutionType, setPollutionType] = useState('smoke');
    const [symptoms, setSymptoms] = useState<string[]>([]);
    const [description, setDescription] = useState('');

    const symptomOptions = ['Coughing', 'Eye Irritation', 'Breathing Difficulty', 'Headache', 'Nausea'];

    const toggleSymptom = (symptom: string) => {
        if (symptoms.includes(symptom)) {
            setSymptoms(symptoms.filter(s => s !== symptom));
        } else {
            setSymptoms([...symptoms, symptom]);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const report = {
            id: Date.now(),
            type: pollutionType,
            symptoms,
            description,
            timestamp: new Date().toISOString(),
            // Mock Location (slightly randomized near center)
            position: [12.9229 + (Math.random() * 0.02 - 0.01), 80.1275 + (Math.random() * 0.02 - 0.01)]
        };
        onSubmit(report);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center backdrop-blur-sm bg-white/30 p-4">
            <div className="bg-white rounded-3xl w-full max-w-md shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
                {/* Header */}
                <div className="bg-rose-500 p-6 text-white flex justify-between items-start">
                    <div>
                        <h2 className="text-xl font-bold flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5" />
                            Report Pollution
                        </h2>
                        <p className="text-rose-100 text-sm mt-1">Help us track unmonitored zones.</p>
                    </div>
                    <button onClick={onClose} className="p-1 hover:bg-white/20 rounded-full transition-colors">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Form */}
                <form onSubmit={handleSubmit} className="p-6 space-y-6">
                    {/* Pollution Type */}
                    <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2">Pollution Type</label>
                        <div className="grid grid-cols-3 gap-3">
                            {['smoke', 'dust', 'odor'].map((type) => (
                                <button
                                    key={type}
                                    type="button"
                                    onClick={() => setPollutionType(type)}
                                    className={`py-3 px-2 rounded-xl text-sm font-medium border-2 transition-all capitalize
                                        ${pollutionType === type
                                            ? 'border-rose-500 bg-rose-50 text-rose-700'
                                            : 'border-gray-100 bg-gray-50 text-gray-500 hover:border-rose-200'}`}
                                >
                                    {type}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Symptoms */}
                    <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2">Health Symptoms</label>
                        <div className="flex flex-wrap gap-2">
                            {symptomOptions.map((symptom) => (
                                <button
                                    key={symptom}
                                    type="button"
                                    onClick={() => toggleSymptom(symptom)}
                                    className={`px-3 py-1.5 rounded-full text-xs font-semibold transition-colors
                                        ${symptoms.includes(symptom)
                                            ? 'bg-rose-100 text-rose-600'
                                            : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}
                                >
                                    {symptom}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Photo Upload */}
                    <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2">Evidence</label>
                        <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 flex flex-col items-center justify-center text-gray-400 hover:bg-gray-50 hover:border-gray-300 transition-colors cursor-pointer">
                            <Camera className="w-8 h-8 mb-2" />
                            <span className="text-xs">Tap to upload photo</span>
                        </div>
                    </div>

                    {/* Submit */}
                    <button
                        type="submit"
                        className="w-full bg-rose-500 text-white py-4 rounded-xl font-bold text-lg shadow-lg shadow-rose-200 hover:bg-rose-600 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
                    >
                        <Send className="w-5 h-5" />
                        Submit Report
                    </button>
                </form>
            </div>
        </div>
    );
};

export default PollutionReportForm;
