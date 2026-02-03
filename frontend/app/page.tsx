'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import FileUpload from '../components/FileUpload';
import YouTubeInput from '../components/YouTubeInput';
import ProgressBar from '../components/ProgressBar';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'file' | 'youtube'>('file');
  const [jobId, setJobId] = useState<string | null>(null);
  const router = useRouter();

  const handleJobComplete = (data: any) => {
    // Redirect to result page
    router.push(`/result/${data.job_id}`);
  };

  return (
    <main className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight sm:text-5xl mb-4">
            Piano Sheet Extractor
          </h1>
          <p className="text-lg text-gray-600">
            Transform your favorite audio into sheet music instantly.
          </p>
        </div>

        {!jobId ? (
          <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => setActiveTab('file')}
                className={`flex-1 py-4 px-6 text-center text-sm font-medium transition-colors duration-200 focus:outline-none ${
                  activeTab === 'file'
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                Upload File
              </button>
              <button
                onClick={() => setActiveTab('youtube')}
                className={`flex-1 py-4 px-6 text-center text-sm font-medium transition-colors duration-200 focus:outline-none ${
                  activeTab === 'youtube'
                    ? 'text-red-600 border-b-2 border-red-600 bg-red-50'
                    : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
                }`}
              >
                YouTube URL
              </button>
            </div>

            <div className="p-8">
              {activeTab === 'file' && (
                <div className="animate-fade-in">
                  <FileUpload onJobCreated={setJobId} />
                </div>
              )}
              
              {activeTab === 'youtube' && (
                <div className="animate-fade-in">
                  <YouTubeInput onJobCreated={setJobId} />
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-2xl shadow-xl p-8 animate-fade-in">
            <h2 className="text-2xl font-bold text-center text-gray-900 mb-6">
              Processing Your Music
            </h2>
            <ProgressBar 
              jobId={jobId} 
              onComplete={handleJobComplete}
            />
            <div className="mt-8 text-center">
              <button 
                onClick={() => setJobId(null)}
                className="text-sm text-gray-500 hover:text-gray-700 underline"
              >
                Cancel and start over
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
