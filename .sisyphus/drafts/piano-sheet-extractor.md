# Draft: 피아노 악보 추출 웹 애플리케이션

## Requirements (confirmed)
- **프로그램 형태**: 웹 애플리케이션 (브라우저에서 파일 업로드 → 결과 확인)
- **입력**: 대중가요 MP3 음원
- **출력 형식**: 
  - MIDI 파일 다운로드
  - MusicXML 파일 다운로드
  - 화면에 악보 표시 (실시간 렌더링)
- **난이도**: 취미로 칠 수 있는 정도 (초중급)

## Technical Decisions
- **오디오→MIDI 변환**: Spotify Basic Pitch (Python 라이브러리)
  - 장점: 오픈소스, 가볍고 빠름, 폴리포닉 지원, 피치벤드 감지
  - pip install basic-pitch로 설치 가능
  - Windows에서는 ONNX 런타임 사용
  - **멜로디 정확도 최적화**: onset/offset threshold 조정, minimum note length 설정
  
- **코드 감지**: chordino 또는 librosa + 자체 알고리즘
  - 오디오에서 코드 진행 자동 감지
  - 사용자가 수정 가능하도록 UI 제공
  
- **악보 렌더링**: OpenSheetMusicDisplay (JavaScript)
  - MusicXML을 브라우저에서 렌더링
  - VexFlow 기반
  - 1000+ GitHub stars, 활발한 유지보수

- **프론트엔드**: Next.js (React 기반)
  - 이유: 풀스택 가능, 포트폴리오에 적합, API Routes로 백엔드 통합 가능
  
- **백엔드**: FastAPI (Python)
  - 이유: Basic Pitch가 Python이므로 자연스러운 선택, 빠르고 현대적

## Research Findings
- **Basic Pitch**: Spotify Audio Intelligence Lab 개발, Apache-2.0 라이선스
  - 실시간보다 빠른 처리 속도
  - 악기 무관하게 작동 (보컬, 피아노, 기타 등)
  - MIDI 출력 지원
  
- **OpenSheetMusicDisplay**: MusicXML → 브라우저 렌더링
  - BSD-3-Clause 라이선스
  - VexFlow 위에 구축됨

## Confirmed Decisions
- [x] 음원 처리: **멜로디 중심 추출** (가장 두드러진 멜로디 라인)
- [x] 난이도 조절: **필요함** (초급/중급/고급 선택 가능)
- [x] 난이도 방식: **음표 간소화** (복잡한 리듬 단순화, 빠른 패시지 생략)
- [x] 코드 표시: **필요함** (악보 위에 C, Am, G7 등 표시)
- [x] 코드 감지: **자동 감지 + 수동 입력/수정 가능**
- [x] BPM 감지: **자동 감지 + 수동 입력/수정 가능**
- [x] 조성(Key) 감지: **자동 감지 + 수동 입력/수정 가능**
- [x] 가사 싱크: **불필요** (악보만 표시)
- [x] 프로젝트 목적: **개인 학습/포트폴리오** (로컬 개발 우선)
- [x] 테스트 전략: **Playwright E2E + Golden Test (정답 악보 비교)**
  - 정답 형식: MIDI, MusicXML 둘 다 지원
  - 비교 모드 1: 유사도 기반 (90%+ 일치, pitch/timing 허용 오차)
  - 비교 모드 2: 핵심 멜로디만 비교
  - 테스트 곡: 10곡 이상 준비
  - **무한 반복 검증**: 정답과 동일해질 때까지 문제 검증 및 수정

## Confirmed (from Metis Review)
- [x] 파일 제한: **50MB / 10분**
- [x] 처리 시간: **5분까지 허용** (CPU 처리 OK)
- [x] 배포 환경: **로컬 Docker**
- [x] 사용자 인증: **MVP에서 제외**
- [x] 변환 히스토리: **MVP에서 제외**

## Scope Boundaries
- INCLUDE: 
  - MP3 업로드 기능 (최대 50MB, 10분)
  - **YouTube URL 입력** (yt-dlp로 오디오 추출)
  - 멜로디 추출 및 MIDI 변환 (Basic Pitch)
  - **멜로디 정확도 최적화** (핵심 요구사항)
  - 난이도 조절 (초급/중급/고급) - 음표 간소화 방식
  - **코드**: 자동 감지 + 수동 입력/수정
  - **BPM**: 자동 감지 + 수동 입력/수정
  - **조성(Key)**: 자동 감지 + 수동 입력/수정
  - MIDI 다운로드
  - MusicXML 다운로드
  - 브라우저 악보 렌더링 (OpenSheetMusicDisplay)
  - Playwright E2E 테스트
  - Docker 기반 로컬 배포
  
- EXCLUDE: 
  - 가사 싱크
  - 사용자 인증
  - 변환 히스토리 저장
  - 다중 트랙 분리 (멜로디만 추출)
  - 실시간 스트리밍 처리
  - PDF 출력 (MusicXML로 MuseScore에서 변환 가능)
  - 모바일 최적화 (데스크톱 웹 우선)
  - Spotify URL 지원 (API 제한)

## YouTube URL 지원 검토 결과

### 검토 완료: ✅ 포함
- 기술적으로 yt-dlp로 구현 가능
- 개인 학습/포트폴리오 목적 + 로컬 Docker 실행
- 면책 조항 추가하여 사용자 책임 명시

## Architecture Sketch
```
[Frontend - React/Next.js]
    ↓ MP3 업로드
[Backend - Python FastAPI]
    ↓ Basic Pitch로 MIDI 변환
    ↓ MIDI → MusicXML 변환
    ↓ (옵션) 난이도 조절 처리
[Frontend]
    ← MIDI, MusicXML 다운로드
    ← OpenSheetMusicDisplay로 악보 렌더링
```
