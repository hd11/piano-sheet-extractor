
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
