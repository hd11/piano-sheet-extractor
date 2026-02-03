'use client';

import { useState } from 'react';

interface DownloadButtonsProps {
  jobId: string;
  difficulty: 'easy' | 'medium' | 'hard';
  originalFilename?: string;
}

export default function DownloadButtons({ jobId, difficulty, originalFilename }: DownloadButtonsProps) {
  const [downloading, setDownloading] = useState<'midi' | 'musicxml' | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async (format: 'midi' | 'musicxml') => {
    try {
      setError(null);
      setDownloading(format);

      // Fetch file from API
      const response = await fetch(`/api/download/${jobId}/${format}?difficulty=${difficulty}`);

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      // Get blob
      const blob = await response.blob();

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // Set filename
      const extension = format === 'midi' ? 'mid' : 'musicxml';
      const baseName = originalFilename
        ? originalFilename.replace(/\.[^/.]+$/, '') // Remove extension
        : `sheet_${jobId.slice(0, 8)}`;
      a.download = `${baseName}_${difficulty}.${extension}`;

      // Trigger download
      document.body.appendChild(a);
      a.click();

      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      console.error('Download failed:', err);
      setError('다운로드에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <button
          onClick={() => handleDownload('midi')}
          disabled={downloading !== null}
          className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          {downloading === 'midi' ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Downloading...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download MIDI
            </>
          )}
        </button>

        <button
          onClick={() => handleDownload('musicxml')}
          disabled={downloading !== null}
          className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          {downloading === 'musicxml' ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Downloading...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download MusicXML
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-2 text-red-700 text-sm">
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
