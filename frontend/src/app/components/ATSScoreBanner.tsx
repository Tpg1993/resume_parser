import React from 'react';

interface ATSScoreBannerProps {
    score?: number;
    tier?: string;
    missingKeywords?: string[];
    projectedScore?: number;
}

export default function ATSScoreBanner({ score = 0, tier = "Unknown", missingKeywords = [], projectedScore = 0 }: ATSScoreBannerProps) {
    let colorClass = "bg-red-500";
    let bgColorClass = "bg-red-50";
    let borderColorClass = "border-red-200";
    let textColorClass = "text-red-700";
    
    if (tier.toLowerCase() === "strong") {
        colorClass = "bg-green-500";
        bgColorClass = "bg-green-50";
        borderColorClass = "border-green-200";
        textColorClass = "text-green-700";
    } else if (tier.toLowerCase() === "fair" || score >= 50) {
        colorClass = "bg-yellow-500";
        bgColorClass = "bg-yellow-50";
        borderColorClass = "border-yellow-200";
        textColorClass = "text-yellow-700";
    }

    return (
        <div className={`mb-8 p-6 rounded-2xl border shadow-sm ${bgColorClass} ${borderColorClass}`}>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="flex items-center gap-8 border-r border-gray-200/60 pr-8">
                    {/* Current Score Circle */}
                    <div className="flex flex-col items-center gap-2">
                        <h4 className="text-sm font-bold text-gray-700 text-center">Before Edit Match</h4>
                        <div className="relative flex items-center justify-center w-24 h-24 rounded-full bg-white shadow-inner">
                            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                <path
                                    className="text-gray-100"
                                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                />
                                <path
                                    className={`${textColorClass.replace('text-', 'text-')}`}
                                    strokeDasharray={`${score}, 100`}
                                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                    strokeLinecap="round"
                                />
                            </svg>
                            <div className="absolute flex flex-col items-center">
                                <span className="text-2xl font-bold text-gray-800">{score}</span>
                                <span className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">/ 100</span>
                            </div>
                        </div>
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase ${colorClass} text-white`}>
                            {tier}
                        </span>
                    </div>

                    {/* Arrow */}
                    {projectedScore > 0 && (
                        <div className="hidden sm:flex flex-col items-center justify-center pt-4">
                            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                            </svg>
                            <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider mt-1">After Edits</span>
                        </div>
                    )}

                    {/* Projected Score Circle */}
                    {projectedScore > 0 && (
                        <div className="flex flex-col items-center gap-2">
                            <h4 className="text-sm font-bold text-green-700 text-center">After Edit Match</h4>
                            <div className="relative flex items-center justify-center w-24 h-24 rounded-full bg-white shadow-inner">
                                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                    <path
                                        className="text-gray-100"
                                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="3"
                                    />
                                    <path
                                        className="text-green-500"
                                        strokeDasharray={`${projectedScore}, 100`}
                                        d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="3"
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute flex flex-col items-center">
                                    <span className="text-2xl font-bold text-gray-800">{projectedScore}</span>
                                    <span className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">/ 100</span>
                                </div>
                            </div>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase bg-green-500 text-white`}>
                                Strong
                            </span>
                        </div>
                    )}
                </div>

                {missingKeywords && missingKeywords.length > 0 && (
                    <div className="flex-1 bg-white/60 p-4 rounded-xl border border-white">
                        <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">Critical Missing Keywords</h4>
                        <div className="flex flex-wrap gap-2">
                            {missingKeywords.map((kw, i) => (
                                <span key={i} className="inline-flex items-center px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-white border shadow-sm text-gray-700">
                                    <svg className="mr-1.5 h-3.5 w-3.5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                    </svg>
                                    {kw}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
