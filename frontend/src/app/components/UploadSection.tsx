'use client';
import { useState } from 'react';
import DiffViewer from './DiffViewer';

export default function UploadSection() {
    const [file, setFile] = useState<File | null>(null);
    const [jd, setJd] = useState('');
    const [companyName, setCompanyName] = useState('');
    const [hiringManager, setHiringManager] = useState('');
    const [isUploading, setIsUploading] = useState(false);
    const [result, setResult] = useState<any>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setFile(e.target.files[0]);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!file || !jd) {
            alert('Please select a PDF and enter a Job Description');
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

        try {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const response = await fetch(`${apiUrl}/api/upload`, {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            setResult(data);
        } catch (error) {
            console.error('Upload error', error);
            alert('Failed to upload and parse Document');
        } finally {
            setIsUploading(false);
        }
    };
    const downloadCoverLetter = () => {
        if (!result || !result.cover_letter_docx) return;
        
        try {
            // Decode base64 to Blob
            const byteCharacters = atob(result.cover_letter_docx);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
            
            // Create Object URL and trigger download
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Cover_Letter_${companyName ? companyName : 'Role'}.docx`;
            document.body.appendChild(a);
            a.click();
            
            // Cleanup
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (error) {
            console.error('Failed to download cover letter', error);
            alert('Failed to process the download file.');
        }
    };

    return (
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-8 max-w-4xl mx-auto mt-8">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Upload Your Profile</h2>
            <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Existing Resume (PDF)
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
                            hover:file:bg-blue-100 cursor-pointer border border-gray-200 rounded-lg"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Target Company Name (Optional)
                    </label>
                    <input 
                        type="text"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                        placeholder="e.g. Acme Corp"
                        className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-4 border"
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
                        className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-4 border"
                    />
                </div>
                <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                        Job Description
                    </label>
                    <textarea 
                        rows={6}
                        value={jd}
                        onChange={(e) => setJd(e.target.value)}
                        placeholder="Paste the job description here..."
                        className="w-full rounded-lg border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-4 border"
                    />
                </div>
                <button
                    type="submit"
                    disabled={isUploading}
                    className="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                >
                    {isUploading ? 'Analyzing...' : 'Analyze & Suggest Diffs'}
                </button>
            </form>

            {result && (
                <div className="mt-8">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="text-xl font-bold text-gray-800">Analysis Results</h3>
                        {result.cover_letter_docx && (
                            <button
                                onClick={downloadCoverLetter}
                                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
                            >
                                <svg className="mr-2 h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                Download Cover Letter (.docx)
                            </button>
                        )}
                    </div>
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
