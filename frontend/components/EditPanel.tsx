'use client';

import { useState, useEffect } from 'react';
import { formatTime, parseTime, isValidTimeFormat } from '@/utils/timeFormat';

interface ChordInfo {
  time: number;
  duration: number;
  chord: string;
  confidence: number;
}

interface AnalysisData {
  bpm: number;
  bpm_confidence: number;
  key: string;
  key_confidence: number;
  chords: ChordInfo[];
}

interface EditPanelProps {
  jobId: string;
  initialData: AnalysisData;
  onSave: (data: AnalysisData) => Promise<void>;
  disabled?: boolean;
}

const KEYS = [
  'C major', 'C# major', 'D major', 'D# major', 'E major', 'F major',
  'F# major', 'G major', 'G# major', 'A major', 'A# major', 'B major',
  'C minor', 'C# minor', 'D minor', 'D# minor', 'E minor', 'F minor',
  'F# minor', 'G minor', 'G# minor', 'A minor', 'A# minor', 'B minor',
];

export default function EditPanel({ jobId, initialData, onSave, disabled }: EditPanelProps) {
  const [bpm, setBpm] = useState(initialData.bpm);
  const [key, setKey] = useState(initialData.key);
  const [chords, setChords] = useState<ChordInfo[]>(initialData.chords);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset when initialData changes
  useEffect(() => {
    setBpm(initialData.bpm);
    setKey(initialData.key);
    setChords(initialData.chords);
  }, [initialData]);

  const handleAddChord = () => {
    const newChord: ChordInfo = {
      time: chords.length > 0 ? chords[chords.length - 1].time + 2 : 0,
      duration: 2.0,
      chord: 'C',
      confidence: 1.0,
    };
    setChords([...chords, newChord]);
  };

  const handleRemoveChord = (index: number) => {
    setChords(chords.filter((_, i) => i !== index));
  };

  const handleChordChange = (index: number, field: keyof ChordInfo, value: string | number) => {
    const updated = [...chords];
    if (field === 'time' && typeof value === 'string') {
      // Parse time string to seconds
      try {
        updated[index].time = parseTime(value);
      } catch {
        // Invalid format, ignore
        return;
      }
    } else {
      updated[index] = { ...updated[index], [field]: value };
    }
    setChords(updated);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);

      // Validate BPM
      if (bpm < 40 || bpm > 240) {
        throw new Error('BPM must be between 40 and 240');
      }

      // Sort chords by time
      const sortedChords = [...chords].sort((a, b) => a.time - b.time);

      const updatedData: AnalysisData = {
        bpm,
        bpm_confidence: initialData.bpm_confidence,
        key,
        key_confidence: initialData.key_confidence,
        chords: sortedChords,
      };

      await onSave(updatedData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 p-6 bg-white rounded-lg border border-gray-200 shadow-sm">
      <h2 className="text-xl font-semibold text-gray-900">Edit Music Properties</h2>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* BPM */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          BPM (Tempo)
        </label>
        <input
          type="number"
          min="40"
          max="240"
          step="1"
          value={bpm}
          onChange={(e) => setBpm(parseFloat(e.target.value))}
          disabled={disabled || saving}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
        />
        <p className="text-xs text-gray-500 mt-1">Range: 40-240 BPM</p>
      </div>

      {/* Key */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Key (조성)
        </label>
        <select
          value={key}
          onChange={(e) => setKey(e.target.value)}
          disabled={disabled || saving}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
        >
          {KEYS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </div>

      {/* Chords */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <label className="block text-sm font-medium text-gray-700">
            Chords (코드 진행)
          </label>
          <button
            onClick={handleAddChord}
            disabled={disabled || saving}
            className="px-3 py-1 text-sm bg-blue-500 hover:bg-blue-600 text-white rounded disabled:opacity-50"
          >
            + Add Chord
          </button>
        </div>

        <div className="space-y-2 max-h-64 overflow-y-auto">
          {chords.map((chord, index) => (
            <div key={index} className="flex items-center gap-2 p-2 bg-gray-50 rounded">
              <input
                type="text"
                value={formatTime(chord.time)}
                onChange={(e) => handleChordChange(index, 'time', e.target.value)}
                placeholder="00:00.0"
                disabled={disabled || saving}
                className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
              <input
                type="text"
                value={chord.chord}
                onChange={(e) => handleChordChange(index, 'chord', e.target.value)}
                placeholder="C"
                disabled={disabled || saving}
                className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              />
              <button
                onClick={() => handleRemoveChord(index)}
                disabled={disabled || saving}
                className="px-2 py-1 text-sm text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Time format: mm:ss.s (e.g., 01:30.5 for 90.5 seconds)
        </p>
      </div>

      {/* Save Button */}
      <button
        onClick={handleSave}
        disabled={disabled || saving}
        className="w-full px-4 py-2 bg-green-600 hover:bg-green-700 text-white font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {saving ? 'Saving...' : 'Save Changes'}
      </button>
    </div>
  );
}
