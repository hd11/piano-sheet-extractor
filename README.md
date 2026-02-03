# Piano Sheet Extractor

Extract piano sheet music from audio files (MP3 or YouTube URLs).

## Project Structure

```
/
├── backend/                    # FastAPI backend (Python 3.11)
│   ├── core/                   # Core business logic
│   ├── api/                    # API endpoints
│   ├── tests/
│   │   ├── unit/              # Unit tests
│   │   ├── e2e/               # End-to-end tests
│   │   └── golden/            # Golden test data
│   │       └── data/          # Test audio files (gitignored)
│   ├── scripts/               # Utility scripts
│   ├── main.py                # FastAPI application
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile             # Backend container
├── frontend/                   # Next.js frontend (React 18)
│   ├── app/                   # Next.js app directory
│   ├── components/            # React components
│   ├── package.json           # Node dependencies
│   ├── tsconfig.json          # TypeScript config
│   ├── next.config.js         # Next.js config
│   └── Dockerfile             # Frontend container
├── docker-compose.yml         # Docker Compose orchestration
├── .gitignore                 # Git ignore rules
└── README.md                  # This file
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Python 3.11+ and Node.js 18+ for local development

### Run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Build and start the FastAPI backend on `http://localhost:8000`
- Build and start the Next.js frontend on `http://localhost:3000`

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)

## Development

### Backend Development

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

## Architecture

### Backend
- **Framework**: FastAPI
- **Audio Processing**: Basic Pitch (Spotify), librosa, music21
- **YouTube Support**: yt-dlp
- **Job Processing**: Async task queue with progress tracking

### Frontend
- **Framework**: Next.js 14 with React 18
- **Sheet Music Display**: OpenSheetMusicDisplay
- **Language**: TypeScript

## Features (Planned)

- MP3 file upload (max 50MB, 20 minutes)
- YouTube URL support
- Melody extraction using Basic Pitch
- MIDI and MusicXML output
- Browser-based sheet music display
- BPM, key, and chord detection
- Difficulty levels (easy, medium, hard)
- Progress tracking

## Configuration

### Environment Variables

- `JOB_STORAGE_PATH`: Directory for job storage (default: `/tmp/piano-sheet-jobs`)

### Docker Compose Resources

- **Backend**: 2 CPU, 4GB RAM (limits)
- **Frontend**: 0.5 CPU, 512MB RAM (limits)

## Testing

### Unit Tests
```bash
cd backend
pytest tests/unit/
```

### End-to-End Tests
```bash
cd backend
pytest tests/e2e/
```

### Golden Tests (Smoke Mode)
```bash
cd backend
pytest tests/golden/ -m smoke
```

## License

TBD

## Contact

For questions or issues, please open an issue on GitHub.
