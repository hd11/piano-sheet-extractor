'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import DifficultySelector from '@/components/DifficultySelector';
import EditPanel from '@/components/EditPanel';
import DownloadButtons from '@/components/DownloadButtons';

// SheetViewer must be dynamically imported (SSR disabled)
const SheetViewer = dynamic(() => import('@/components/SheetViewer'), {
  ssr: false,
  loading: () => (
    <div className="flex flex-col items-center justify-center h-[400px] bg-gray-50 rounded-xl border border-gray-200">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
      <p className="text-gray-500 font-medium">Loading sheet music viewer...</p>
    </div>
  )
});

export default function ResultPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
  const [musicXml, setMusicXml] = useState<string>('');
  
  // Fetch job result on mount
  useEffect(() => {
    if (jobId) {
      fetchResult();
    }
  }, [jobId]);
  
  // Fetch MusicXML when difficulty changes or result is loaded
  useEffect(() => {
    if (result && jobId) {
      fetchMusicXml(difficulty);
    }
  }, [difficulty, result, jobId]);
  
  const fetchResult = async () => {
    try {
      const res = await fetch(`/api/result/${jobId}`);
      if (!res.ok) {
        if (res.status === 404) throw new Error('Job not found');
        throw new Error('Failed to fetch result');
      }
      const data = await res.json();
      
      if (data.status === 'failed') {
        throw new Error(data.error?.message || 'Processing failed');
      }
      
      setResult(data);
      setLoading(false);
    } catch (err: any) {
      console.error('Fetch result error:', err);
      setError(err.message);
      setLoading(false);
    }
  };
  
  const fetchMusicXml = async (diff: string) => {
    try {
      // Use the download endpoint to get the XML content
      const res = await fetch(`/api/download/${jobId}/musicxml?difficulty=${diff}`);
      if (!res.ok) throw new Error('Failed to fetch MusicXML');
      const xmlText = await res.text();
      setMusicXml(xmlText);
    } catch (err) {
      console.error('Failed to load MusicXML:', err);
      // Don't set global error here, just log it. SheetViewer might handle empty XML or we can show a toast.
    }
  };
  
  const handleEditUpdate = async (updatedData: any) => {
    try {
      const res = await fetch(`/api/result/${jobId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updatedData),
      });
      
      if (!res.ok) throw new Error('Failed to update analysis');
      
      // If update triggers regeneration, we might want to poll or show a loading state
      // For now, just log success
      console.log('Analysis updated, regeneration started');
      
      // Optionally refresh result to get new status if it changes to 'processing'
      fetchResult();
      
    } catch (err) {
      console.error('Update error:', err);
      // EditPanel handles its own error state usually, but we can also show a toast here
    }
  };
  
  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50 py-12 px-4">
        <div className="max-w-6xl mx-auto text-center pt-20">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-6"></div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Loading Result</h2>
          <p className="text-gray-600">Fetching your sheet music...</p>
        </div>
      </main>
    );
  }
  
  if (error || !result) {
    return (
      <main className="min-h-screen bg-gray-50 py-12 px-4">
        <div className="max-w-md mx-auto text-center bg-white p-8 rounded-2xl shadow-xl mt-20">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Error</h1>
          <p className="text-gray-600 mb-6">{error || 'Result not found'}</p>
          <a 
            href="/" 
            className="inline-flex items-center justify-center px-6 py-3 border border-transparent text-base font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 transition-colors"
          >
            Go back home
          </a>
        </div>
      </main>
    );
  }
  
  return (
    <main className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-1">
              Your Sheet Music
            </h1>
            <p className="text-gray-600 flex items-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
              </svg>
              {result.original_filename || 'Processed audio'}
            </p>
          </div>
          
          <a 
            href="/" 
            className="inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-800 transition-colors"
          >
            ← Process another file
          </a>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Content: Sheet Viewer */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <h2 className="text-xl font-bold text-gray-900">Sheet Music</h2>
                <DifficultySelector 
                  value={difficulty} 
                  onChange={setDifficulty} 
                />
              </div>
              
              <div className="min-h-[500px]">
                {musicXml ? (
                  <SheetViewer 
                    musicXml={musicXml}
                    difficulty={difficulty}
                    onError={(err) => console.error('Sheet viewer error:', err)}
                  />
                ) : (
                  <div className="flex flex-col items-center justify-center h-[400px] bg-gray-50 rounded-xl border border-gray-200 border-dashed">
                    <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-gray-400 mb-3"></div>
                    <p className="text-gray-500">Loading MusicXML...</p>
                  </div>
                )}
              </div>
            </div>
          </div>
          
          {/* Sidebar: Controls & Download */}
          <div className="space-y-6">
            {/* Download Card */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download
              </h3>
              <DownloadButtons 
                jobId={jobId}
                difficulty={difficulty}
                originalFilename={result.original_filename}
              />
            </div>

            {/* Edit Panel */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
              <div className="p-6 border-b border-gray-100">
                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                  </svg>
                  Music Properties
                </h3>
              </div>
              <div className="p-0">
                <EditPanel 
                  jobId={jobId}
                  initialData={result.analysis}
                  onSave={handleEditUpdate}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
