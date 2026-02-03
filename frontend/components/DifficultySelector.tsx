'use client';

interface DifficultySelectorProps {
  value: 'easy' | 'medium' | 'hard';
  onChange: (difficulty: 'easy' | 'medium' | 'hard') => void;
  disabled?: boolean;
}

export default function DifficultySelector({ value, onChange, disabled }: DifficultySelectorProps) {
  const difficulties: Array<{ value: 'easy' | 'medium' | 'hard'; label: string; description: string }> = [
    { value: 'easy', label: '초급', description: '단선율, 좁은 음역' },
    { value: 'medium', label: '중급', description: '최대 2음, 넓은 음역' },
    { value: 'hard', label: '고급', description: '원본 그대로' },
  ];

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        난이도
      </label>
      <div className="grid grid-cols-3 gap-2">
        {difficulties.map((diff) => (
          <button
            key={diff.value}
            onClick={() => onChange(diff.value)}
            disabled={disabled}
            className={`
              px-4 py-3 rounded-lg border-2 transition-all text-left
              ${value === diff.value
                ? 'border-blue-500 bg-blue-50 text-blue-900'
                : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
              }
              ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            <div className="font-semibold text-sm">{diff.label}</div>
            <div className="text-xs text-gray-500 mt-1">{diff.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
