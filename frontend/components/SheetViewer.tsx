'use client';

import { useEffect, useRef, useState } from 'react';
import { OpenSheetMusicDisplay } from 'opensheetmusicdisplay';

interface SheetViewerProps {
  musicXml: string;           // MusicXML string
  difficulty?: 'easy' | 'medium' | 'hard';  // Difficulty level
  onError?: (error: Error) => void;         // Error handler
}

export default function SheetViewer({ musicXml, difficulty, onError }: SheetViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const osmdRef = useRef<OpenSheetMusicDisplay | null>(null);
  const [zoom, setZoom] = useState(1.0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize OSMD
  useEffect(() => {
    if (!containerRef.current || !musicXml) return;

    let isMounted = true;

    const loadSheet = async () => {
      try {
        setLoading(true);
        setError(null);

        // Clear previous content if any
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
        }

        // Create OSMD instance
        // We need to ensure the container is empty before creating a new instance
        // or handle re-initialization properly. 
        // For simplicity and robustness, we recreate it when musicXml changes.
        const osmd = new OpenSheetMusicDisplay(containerRef.current!, {
          autoResize: true,
          backend: 'svg',
          drawTitle: true,
          drawingParameters: 'compacttight', // More compact rendering
        });

        // Load MusicXML
        await osmd.load(musicXml);
        
        if (isMounted) {
          await osmd.render();
          osmdRef.current = osmd;
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          const errorMsg = err instanceof Error ? err.message : 'Failed to load sheet music';
          console.error('OSMD Error:', err);
          setError(errorMsg);
          onError?.(err instanceof Error ? err : new Error(errorMsg));
          setLoading(false);
        }
      }
    };

    loadSheet();

    // Cleanup
    return () => {
      isMounted = false;
      osmdRef.current = null;
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [musicXml, onError]);

  // Handle zoom
  useEffect(() => {
    if (osmdRef.current) {
      try {
        osmdRef.current.zoom = zoom;
        osmdRef.current.render();
      } catch (e) {
        console.warn('Zoom render failed:', e);
      }
    }
  }, [zoom]);

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.1, 2.0));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.1, 0.5));
  const handleResetZoom = () => setZoom(1.0);

  // Difficulty badge colors
  const difficultyColors = {
    easy: 'bg-green-100 text-green-800 border-green-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    hard: 'bg-red-100 text-red-800 border-red-200',
  };

  return (
    <div className="w-full flex flex-col gap-4">
      {/* Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200 shadow-sm">
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-white rounded-md border border-gray-300 overflow-hidden shadow-sm">
            <button
              onClick={handleZoomOut}
              disabled={zoom <= 0.5 || loading}
              className="px-3 py-1.5 hover:bg-gray-100 active:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors border-r border-gray-200 text-gray-700 font-medium"
              aria-label="Zoom out"
            >
              −
            </button>
            <span className="w-16 text-center text-sm font-mono text-gray-600 select-none">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={handleZoomIn}
              disabled={zoom >= 2.0 || loading}
              className="px-3 py-1.5 hover:bg-gray-100 active:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors border-l border-gray-200 text-gray-700 font-medium"
              aria-label="Zoom in"
            >
              +
            </button>
          </div>
          
          <button
            onClick={handleResetZoom}
            disabled={loading}
            className="px-3 py-1.5 text-sm text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50 hover:text-gray-900 transition-colors shadow-sm disabled:opacity-50"
          >
            Reset
          </button>
        </div>

        {difficulty && (
          <div className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide border ${difficultyColors[difficulty] || 'bg-gray-100 text-gray-800 border-gray-200'}`}>
            {difficulty}
          </div>
        )}
      </div>

      {/* Sheet Container */}
      <div className="relative w-full min-h-[400px] bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/90 backdrop-blur-sm transition-opacity">
            <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-3"></div>
            <div className="text-gray-500 font-medium animate-pulse">Rendering Sheet Music...</div>
          </div>
        )}
        
        {error && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-red-50/90 backdrop-blur-sm p-6">
            <div className="max-w-md text-center">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-red-100 mb-4">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-red-900 mb-2">Unable to Load Sheet Music</h3>
              <p className="text-sm text-red-700 bg-red-100 p-3 rounded border border-red-200 font-mono break-all">
                {error}
              </p>
            </div>
          </div>
        )}

        <div 
          ref={containerRef} 
          className="w-full h-full overflow-auto p-4 md:p-8 bg-white"
          style={{ minHeight: '400px' }}
        />
      </div>
    </div>
  );
}
