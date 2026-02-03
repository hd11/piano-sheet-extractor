'use client';

import { useEffect, useState } from 'react';

interface ProgressBarProps {
  jobId: string;
  onComplete: (data: any) => void;
}

export default function ProgressBar({ jobId, onComplete }: ProgressBarProps) {
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState('Initializing...');
  const [status, setStatus] = useState('pending');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const pollStatus = async () => {
      try {
        const response = await fetch(`/api/status/${jobId}`);
        if (!response.ok) {
          throw new Error('Failed to fetch status');
        }
        const data = await response.json();

        setProgress(data.progress || 0);
        setStage(data.current_stage || 'Processing...');
        setStatus(data.status);

        if (data.status === 'completed') {
          clearInterval(intervalId);
          onComplete(data);
        } else if (data.status === 'failed') {
          clearInterval(intervalId);
          setError(data.error || 'Job failed');
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    pollStatus(); // Initial call
    const intervalId = setInterval(pollStatus, 1000); // Poll every 1s

    return () => clearInterval(intervalId);
  }, [jobId, onComplete]);

  if (error) {
    return (
      <div className="w-full max-w-xl mx-auto mt-8 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
        <p className="font-bold">Error:</p>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-xl mx-auto mt-8 space-y-2">
      <div className="flex justify-between text-sm font-medium text-gray-700">
        <span>{stage}</span>
        <span>{Math.round(progress)}%</span>
      </div>
      
      <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
        <div
          className="bg-blue-600 h-4 rounded-full transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      
      <p className="text-xs text-gray-500 text-right">
        Status: <span className="uppercase">{status}</span>
      </p>
    </div>
  );
}
