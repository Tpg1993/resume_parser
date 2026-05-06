import React from 'react';

interface Suggestion {
    section?: string;
    role?: string | null;
    company?: string | null;
    original?: string | null;
    suggested?: string;
    reasoning?: string;
}

export default function DiffViewer({ suggestions }: { suggestions: Suggestion[] }) {
    if (!suggestions || suggestions.length === 0) return null;

    return (
        <div className="mt-8 space-y-6">
            <h3 className="text-xl font-bold text-gray-800 border-b pb-2">AI Suggested Modifications</h3>
            {suggestions.map((sug, idx) => (
                <div key={idx} className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow">
                    <div className="bg-gradient-to-r from-blue-50 to-indigo-50 px-5 py-3 border-b border-indigo-100 flex justify-between items-center">
                        <div className="flex flex-col gap-0.5">
                            <span className="font-semibold text-indigo-800">Section: {sug.section || 'General'}</span>
                            {(sug.role || sug.company) && (
                                <span className="text-xs text-indigo-600 font-medium">
                                    {[sug.role, sug.company].filter(Boolean).join(' · ')}
                                </span>
                            )}
                        </div>
                        <span className="px-2.5 py-1 bg-indigo-100 text-indigo-800 text-[10px] font-bold rounded-md uppercase tracking-wider">
                            Targeted Update
                        </span>
                    </div>
                    <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-red-50/50 p-4 rounded-lg border border-red-100/50">
                            <h4 className="text-xs font-bold text-red-600 uppercase tracking-wider mb-2">Original Context</h4>
                            <p className="text-sm text-red-900 whitespace-pre-wrap">{sug.original || '— (New Addition)'}</p>
                        </div>
                        <div className="bg-green-50/50 p-4 rounded-lg border border-green-100/50">
                            <h4 className="text-xs font-bold text-green-600 uppercase tracking-wider mb-2">Suggested Revision</h4>
                            <p className="text-sm text-green-900 whitespace-pre-wrap">{sug.suggested || '—'}</p>
                        </div>
                    </div>
                    {sug.reasoning && (
                        <div className="bg-gray-50/80 px-5 py-3 border-t border-gray-100 text-sm text-gray-600 italic">
                            <span className="font-semibold not-italic">Why:</span> {sug.reasoning}
                        </div>
                    )}
                </div>
            ))}
        </div>
    );
}
