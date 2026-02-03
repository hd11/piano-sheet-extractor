
## [2026-02-03] Task 10: SheetViewer Component Implementation

### Implementation Details
- **Component**: `frontend/components/SheetViewer.tsx`
- **Library**: `opensheetmusicdisplay` (OSMD)
- **Features**:
  - MusicXML rendering from string
  - Zoom controls (50% - 200%)
  - Responsive container
  - Loading and Error states
  - Difficulty badge
- **Key Technical Decisions**:
  - **'use client'**: Required for OSMD as it accesses window/document
  - **Dynamic Import**: Consumer must use `next/dynamic` with `ssr: false`
  - **Cleanup**: Explicitly clear container innerHTML on unmount/re-render to prevent duplicate sheets
  - **Styling**: Tailwind CSS for controls and container
  - **Zoom Handling**: Updates `osmd.zoom` and calls `render()` without full reload

### Usage Example
```typescript
import dynamic from 'next/dynamic';

const SheetViewer = dynamic(() => import('@/components/SheetViewer'), {
  ssr: false,
  loading: () => <div>Loading...</div>
});

// In component
<SheetViewer 
  musicXml={xmlString} 
  difficulty="medium" 
  onError={(e) => console.error(e)} 
/>
```

## Frontend UI Components
- Implemented `DifficultySelector` for selecting difficulty levels (easy, medium, hard).
- Implemented `EditPanel` for editing BPM, Key, and Chords.
- Created `timeFormat` utility for converting between seconds and mm:ss.s format.
- Used `padEnd` and `toFixed` for precise time formatting.
- Added validation for BPM (40-240) and time format.

## [2026-02-03] Task 12: DownloadButtons Component Implementation

### Implementation Details
- **Component**: `frontend/components/DownloadButtons.tsx`
- **Features**:
  - MIDI download button (blue)
  - MusicXML download button (green)
  - Native browser download using `<a>` element with `download` attribute
  - Loading states with spinner animation
  - Error handling with user-friendly Korean messages
  - Filename format: `{baseName}_{difficulty}.{extension}`
  - Proper blob cleanup with `URL.revokeObjectURL()`

### Key Technical Decisions
- **No External Libraries**: Uses native browser APIs (fetch, Blob, URL.createObjectURL)
- **'use client'**: Required for browser APIs (window, document)
- **State Management**: 
  - `downloading`: Tracks which format is being downloaded (prevents simultaneous downloads)
  - `error`: Displays error messages to user
- **Filename Logic**:
  - If `originalFilename` provided: strips extension and appends `_{difficulty}.{ext}`
  - Fallback: uses `sheet_{jobId.slice(0, 8)}_{difficulty}.{ext}`
- **API Endpoint**: `GET /api/download/{jobId}/{format}?difficulty={difficulty}`
- **Styling**: Matches existing component patterns (Tailwind CSS, disabled states, transitions)

### Props Interface
```typescript
interface DownloadButtonsProps {
  jobId: string;                    // Job ID from upload
  difficulty: 'easy' | 'medium' | 'hard';  // Selected difficulty
  originalFilename?: string;        // Optional original filename for better naming
}
```

### Usage Example
```typescript
<DownloadButtons 
  jobId="abc123def456"
  difficulty="medium"
  originalFilename="my_song.mp3"
/>
```

### Error Handling
- Network errors: Caught and displayed as "다운로드에 실패했습니다. 다시 시도해주세요."
- Disabled state during download prevents multiple simultaneous requests
- Error message clears when user attempts new download

### TypeScript Verification
- ✅ `npx tsc --noEmit` passes with no errors
- ✅ Strict type checking enabled
- ✅ Proper React hooks typing
