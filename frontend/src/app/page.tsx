import UploadSection from './components/UploadSection';

export default function Home() {
  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center">
      <header className="w-full bg-white shadow-sm font-sans flex items-center justify-center p-6 border-b">
        <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">
          Agentic Resume Builder
        </h1>
      </header>
      <div className="flex-1 w-full max-w-7xl px-4 py-8">
        <UploadSection />
      </div>
    </main>
  );
}
