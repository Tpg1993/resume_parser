'use client';
import { useState } from 'react';
import DiffViewer from './DiffViewer';
import ATSScoreBanner from './ATSScoreBanner';

export default function UploadSection() {
    const [file, setFile] = useState<File | null>(null);
    const [jd, setJd] = useState('');
    const [companyName, setCompanyName] = useState('');
    const [hiringManager, setHiringManager] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [result, setResult] = useState<any>(null);

    // Scraping states
    const [jobUrl, setJobUrl] = useState('');
    const [isScraping, setIsScraping] = useState(false);
    const [scrapingError, setScrapingError] = useState('');
    const [originalLength, setOriginalLength] = useState<number | null>(null);
    const [condensedLength, setCondensedLength] = useState<number | null>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    const handleImportJob = async (e: React.MouseEvent) => {
        e.preventDefault();
        if (!jobUrl) {
            alert('Please enter a valid Job URL first.');
            return;
        }

        setIsScraping(true);
        setScrapingError('');
        setOriginalLength(null);
        setCondensedLength(null);

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001';
            const response = await fetch(`${apiUrl}/api/scrape-job`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: jobUrl }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to extract job details.');
            }

            const data = await response.json();
            setJd(data.condensed_jd || '');
            // Keep company and manager name blank by default so cover letter generation is not triggered
            // if (data.company) {
            //     setCompanyName(data.company);
            // }
            setOriginalLength(data.original_length);
            setCondensedLength(data.condensed_length);
        } catch (error: any) {
            console.error('Import error:', error);
            setScrapingError(error.message || 'Error occurred while scraping the job posting.');
        } finally {
            setIsScraping(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file) {
            alert('Please select a PDF Resume to upload');
            return;
        }
        if (!jd.trim()) {
            alert('Please enter or import a Job Description');
            return;
        }

        setIsUploading(true);
        const formData = new FormData();
        formData.append('resume', file);
        formData.append('jd', jd);
        if (companyName) {
            formData.append('company_name', companyName);
        }
        if (hiringManager) {
            formData.append('hiring_manager', hiringManager);
        }
        if (jobUrl) {
            formData.append('job_url', jobUrl);
        }

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8001';
            const response = await fetch(`${apiUrl}/api/upload`, {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            if (response.status !== 200) {
                throw new Error(data.detail || 'Analysis execution failed');
            }
            setResult(data);
        } catch (error: any) {
            console.error('Upload error', error);
            alert(`Failed to analyze resume: ${error.message || error}`);
        } finally {
            setIsUploading(false);
        }
    };

    const downloadCoverLetter = () => {
        if (!result || !result.cover_letter_docx) return;
        
        try {
            const byteCharacters = atob(result.cover_letter_docx);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Cover_Letter_${companyName ? companyName.replace(/\s+/g, '_') : 'Role'}.docx`;
            document.body.appendChild(a);
            a.click();
            
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Failed to download cover letter', error);
            alert('Failed to process the download file.');
        }
    };

    const reductionPercent = originalLength && condensedLength 
        ? Math.round(((originalLength - condensedLength) / originalLength) * 100)
        : 0;

    return (
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8 max-w-4xl mx-auto mt-8 font-sans">
            <div className="border-b border-gray-100 pb-6 mb-6">
                <h2 className="text-2xl font-bold text-gray-800">Job-Tailored Resume Optimizer</h2>
                <p className="text-gray-500 text-sm mt-1">
                    Phase 1: Import & extract requirements. Phase 2: Tailor your resume.
                </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* PHASE 1: JOB DETAILS ACQUISITION */}
                <div className="bg-blue-50/50 rounded-xl p-5 border border-blue-100/50 space-y-4">
                    <h3 className="text-sm font-bold text-blue-800 uppercase tracking-wider">
                        Phase 1: Job Description / URL
                    </h3>
                    
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Job URL (LinkedIn, Indeed, Career Sites...)
                        </label>
                        <div className="flex gap-3">
                            <input 
                                type="url"
                                value={jobUrl}
                                onChange={(e) => setJobUrl(e.target.value)}
                                placeholder="https://www.linkedin.com/jobs/view/..."
                                className="flex-1 rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm px-4 py-3 border bg-white"
                            />
                            <button
                                type="button"
                                onClick={handleImportJob}
                                disabled={isScraping}
                                className="px-5 py-3 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 rounded-lg shadow transition flex items-center gap-2 whitespace-nowrap"
                            >
                                {isScraping ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                        </svg>
                                        Extracting...
                                    </>
                                ) : 'Import & Condense'}
                            </button>
                        </div>
                    </div>

                    {scrapingError && (
                        <div className="bg-red-50 text-red-700 text-xs p-3 rounded-lg border border-red-100">
                            ⚠️ {scrapingError}
                        </div>
                    )}

                    {originalLength !== null && condensedLength !== null && (
                        <div className="bg-green-50 text-green-800 text-xs p-3 rounded-lg border border-green-100 flex items-center justify-between">
                            <span>
                                ✨ <strong>Scraping successful!</strong> Job description reduced from <strong>{originalLength}</strong> to <strong>{condensedLength}</strong> characters.
                            </span>
                            <span className="bg-green-200 text-green-900 px-2 py-0.5 rounded-full font-bold">
                                📉 -{reductionPercent}% tokens saved
                            </span>
                        </div>
                    )}
                </div>

                {/* PHASE 2: REVIEW & EDIT AND RESUME UPLOAD */}
                <div className="space-y-6">
                    <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider border-b pb-2">
                        Phase 2: Tailoring & Verification
                    </h3>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                                Target Company Name
                            </label>
                            <input 
                                type="text"
                                value={companyName}
                                onChange={(e) => setCompanyName(e.target.value)}
                                placeholder="e.g. Acme Corp (pre-filled from URL)"
                                className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm p-3 border"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">
                                Hiring Manager Name (Optional)
                            </label>
                            <input 
                                type="text"
                                value={hiringManager}
                                onChange={(e) => setHiringManager(e.target.value)}
                                placeholder="e.g. Kaitlynn Lim"
                                className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm p-3 border"
                            />
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between items-center mb-2">
                            <label className="block text-sm font-semibold text-gray-700">
                                Job Description & Necessary Requirements
                            </label>
                            {jd && (
                                <span className="text-xs bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded-full font-medium">
                                    Core Requirements Extracted
                                </span>
                            )}
                        </div>
                        <textarea 
                            rows={8}
                            value={jd}
                            onChange={(e) => setJd(e.target.value)}
                            placeholder="Paste description manually or extract via URL above..."
                            className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm p-4 border bg-gray-50/20 font-mono"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">
                            Upload Existing Resume (PDF)
                        </label>
                        <input 
                            type="file" 
                            accept="application/pdf"
                            onChange={handleFileChange}
                            className="block w-full text-sm text-gray-500
                                file:mr-4 file:py-2.5 file:px-4
                                file:rounded-full file:border-0
                                file:text-sm file:font-semibold
                                file:bg-blue-50 file:text-blue-700
                                hover:file:bg-blue-100 cursor-pointer border border-gray-200 rounded-lg bg-gray-50/10"
                        />
                    </div>
                </div>

                <button
                    type="submit"
                    disabled={isUploading}
                    className="w-full flex justify-center py-3.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition"
                >
                    {isUploading ? (
                        <span className="flex items-center gap-2">
                            <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            Analyzing & Tailoring Resume...
                        </span>
                    ) : 'Run Match & Suggest Changes'}
                </button>
            </form>

            {result && (
                <div className="mt-8 border-t border-gray-100 pt-8">
                    {result.ats_score !== undefined && (
                        <ATSScoreBanner 
                            score={result.ats_score} 
                            tier={result.match_tier} 
                            missingKeywords={result.missing_keywords} 
                            projectedScore={result.projected_score}
                        />
                    )}
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="text-xl font-bold text-gray-800">Analysis Results</h3>
                        {result.cover_letter_docx && (
                            <button
                                onClick={downloadCoverLetter}
                                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-semibold rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition"
                            >
                                <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                Download Cover Letter (.docx)
                            </button>
                        )}
                    </div>

                    {result.cover_letter_data && (
                        <div className="mb-8 bg-slate-50 border border-slate-200 rounded-xl p-6 shadow-sm">
                            <div className="flex justify-between items-center border-b border-slate-200 pb-4 mb-4">
                                <div>
                                    <h4 className="text-lg font-bold text-slate-800">Generated Cover Letter Preview</h4>
                                    <p className="text-xs text-slate-500">Executive 1-page layout formatted for high impact</p>
                                </div>
                                <button
                                    onClick={() => {
                                        const clData = result.cover_letter_data;
                                        const text = `${clData.candidate_name}\n${clData.candidate_title || ''}\n${clData.contact_info || ''}\n\n${clData.greeting || ''}\n\n${(clData.body_paragraphs || []).join('\n\n')}\n\n${clData.sign_off || ''}`;
                                        navigator.clipboard.writeText(text);
                                        alert('Cover Letter copied to clipboard!');
                                    }}
                                    className="inline-flex items-center px-3 py-1.5 border border-slate-300 text-xs font-medium rounded text-slate-700 bg-white hover:bg-slate-100 transition shadow-sm"
                                >
                                    Copy Plain Text
                                </button>
                            </div>

                            <div className="bg-white p-6 rounded-lg border border-slate-200 font-sans text-slate-800 text-sm leading-relaxed max-w-2xl mx-auto shadow-inner">
                                <div className="text-slate-900 font-bold text-xl">{result.cover_letter_data.candidate_name}</div>
                                {result.cover_letter_data.candidate_title && (
                                    <div className="text-slate-500 italic text-sm mb-1">{result.cover_letter_data.candidate_title}</div>
                                )}
                                {result.cover_letter_data.contact_info && (
                                    <div className="text-xs text-slate-500 pb-3 mb-4 border-b border-slate-200">
                                        {result.cover_letter_data.contact_info}
                                    </div>
                                )}

                                <div className="text-xs text-slate-500 mb-3">
                                    {new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}
                                </div>

                                <div className="font-semibold text-slate-800 mb-4">
                                    {hiringManager && hiringManager.trim().toLowerCase() !== 'hiring manager' ? (
                                        <>
                                            <div>{hiringManager}</div>
                                            <div>Hiring Manager{companyName ? `, ${companyName}` : ''}</div>
                                        </>
                                    ) : (
                                        <>
                                            <div>Hiring Manager</div>
                                            {companyName && <div>{companyName}</div>}
                                        </>
                                    )}
                                </div>

                                <div className="font-medium text-slate-900 mb-3">
                                    {result.cover_letter_data.greeting}
                                </div>

                                <div className="space-y-3 text-slate-700">
                                    {(result.cover_letter_data.body_paragraphs || []).map((para: string, idx: number) => (
                                        <p key={idx}>
                                            {para.split(/(\*\*.*?\*\*)/g).map((part, pIdx) => {
                                                if (part.startsWith('**') && part.endsWith('**')) {
                                                    return <strong key={pIdx} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
                                                }
                                                return part;
                                            })}
                                        </p>
                                    ))}
                                </div>

                                <div className="mt-6 whitespace-pre-line text-slate-800 font-medium">
                                    {result.cover_letter_data.sign_off}
                                </div>
                            </div>
                        </div>
                    )}

                    {result.suggestions && result.suggestions.length > 0 ? (
                        <DiffViewer suggestions={result.suggestions} />
                    ) : (
                        <>
                            <h3 className="font-bold text-gray-700 mb-2">Parsed Output Preview:</h3>
                            <div className="p-6 bg-gray-50 rounded-lg whitespace-pre-wrap font-mono text-sm border max-h-[600px] overflow-y-auto">
                                {result.parsed_content || JSON.stringify(result, null, 2)}
                            </div>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
