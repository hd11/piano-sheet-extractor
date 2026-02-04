# Learnings - Golden Test MusicXML

## Task 1: MusicXML Comparator Module

### music21 Patterns for MusicXML Parsing

1. **Parsing MXL/MusicXML files**:
   ```python
   score = music21.converter.parse(file_path)
   ```
   - MXL (compressed MusicXML) is handled automatically
   - Returns a `music21.stream.Score` object

2. **Extracting notes**:
   ```python
   for element in score.flatten().notes:
       if isinstance(element, music21.note.Note):
           pitch = element.pitch.midi  # MIDI pitch (0-127)
           onset = element.offset  # quarterLength units
           duration = element.duration.quarterLength
   ```

3. **Handling Chords**:
   - Chords contain multiple pitches at the same onset
   - Access via `element.pitches` for individual pitch objects

4. **Metadata extraction**:
   - Time signature: `score.flatten().getElementsByClass(music21.meter.TimeSignature)`
   - Key: `score.flatten().getElementsByClass(music21.key.Key)`
   - KeySignature fallback: `ks.asKey()` to infer Key from KeySignature

5. **Measure count**:
   - Check `score.getElementsByClass(music21.stream.Measure)`
   - If empty, iterate through `score.parts` to find measures

### Note Matching Algorithm

- Greedy matching with tolerance-based comparison
- Pitch must match exactly (MIDI numbers)
- Onset tolerance: 0.1 quarterLength (~100ms at 60 BPM)
- Duration tolerance: 20% ratio
- Track used indices to prevent duplicate matching

### Test Data Characteristics

- song_01/reference.mxl contains 2040 notes
- Includes time signature (4/4) and key information
- Proper measure structure for structural comparison

### Environment Notes

- Windows environment requires `uv run python` for consistent execution
- Python 3.11 required for tensorflow compatibility (basic-pitch dependency)
- music21 is already in requirements.txt
## [2026-02-04] Task 1: MusicXML Comparator 모듈 구현

### 구현 완료
- `backend/core/musicxml_comparator.py` 신규 생성
- music21 라이브러리를 사용한 MXL/MusicXML 파싱
- 음표 기반 비교 + 구조적 비교 구현

### 주요 기술 결정
1. **quarterLength 단위 사용**: BPM 독립적 비교를 위해 music21의 내부 단위 사용
2. **Chord 처리**: Chord를 개별 Note로 분해하여 비교 (line 111-120)
3. **Greedy Matching**: 각 reference 노트에 대해 가장 가까운 generated 노트 찾기
4. **허용 오차**: onset ±0.1 quarterLength, duration ±20%

### 검증 결과
- ✅ 모듈 import 성공
- ✅ 동일 파일 비교 시 100% 유사도 (2040 notes)
- ✅ 에러 처리 정상 동작 (ComparisonError)

### music21 사용 패턴
```python
# MXL 파일 파싱 (자동으로 ZIP 압축 해제)
score = music21.converter.parse(file_path)

# 음표 추출
for element in score.flatten().notes:
    if isinstance(element, music21.note.Note):
        pitch = element.pitch.midi
        onset = element.offset  # quarterLength
        duration = element.duration.quarterLength

# 메타데이터 추출
time_sigs = score.flatten().getElementsByClass(music21.meter.TimeSignature)
keys = score.flatten().getElementsByClass(music21.key.Key)
```

### 발견한 이슈
- 없음 (모든 테스트 통과)


## [2026-02-04] Task 2: Golden Test Compare Mode Implementation

### Pytest Parametrize Pattern

1. **Basic parametrize syntax**:
   ```python
   @pytest.mark.parametrize(
       "param_name",
       [value1, value2, value3],
       ids=lambda v: v  # Custom test ID function
   )
   def test_function(self, param_name):
       pass
   ```

2. **Multiple parameters**:
   ```python
   @pytest.mark.parametrize(
       "param1,param2",
       [(val1, val2), (val3, val4)]
   )
   ```

3. **Fixture integration**:
   - Parametrized tests can use fixtures alongside parametrized parameters
   - Fixtures are resolved after parametrization
   - Example: `def test_func(self, param, fixture_name)`

### Conftest Fixture Pattern

1. **Session-scoped fixture**:
   ```python
   @pytest.fixture(scope="session")
   def golden_data_dir():
       data_dir = Path(__file__).parent / "data"
       if not data_dir.exists():
           pytest.skip("Directory not found")
       return data_dir
   ```

2. **Marker registration**:
   ```python
   def pytest_configure(config):
       config.addinivalue_line("markers", "compare: Compare test marker")
   ```

### Test Class Structure

1. **Class-level markers**:
   ```python
   @pytest.mark.golden
   @pytest.mark.compare
   class TestGoldenCompare:
       """Test class with multiple markers"""
   ```

2. **Method-level markers**:
   - Can be combined with class-level markers
   - Parametrize decorator on methods works with class-based tests

### Discovered Issues

- Korean characters in docstrings can cause parsing issues in some environments
- Use ASCII-only docstrings for maximum compatibility
- File encoding declaration (`# -*- coding: utf-8 -*-`) helps but isn't always sufficient
- Pytest discovery requires proper indentation and syntax

### Best Practices

1. Keep docstrings ASCII-only for test files
2. Use `ids=lambda x: x` for readable test IDs in parametrize
3. Session-scoped fixtures are efficient for shared test data
4. Marker registration in pytest_configure ensures markers are recognized
5. Test class names must start with "Test" for pytest discovery


## [2026-02-04] Task 2: Golden Test compare 모드 추가

### 구현 완료
- `backend/tests/golden/conftest.py`: compare 마커 등록, golden_data_dir fixture 추가
- `backend/tests/golden/test_golden.py`: TestGoldenCompare 클래스 추가

### pytest 패턴
```python
# 마커 등록
def pytest_configure(config):
    config.addinivalue_line("markers", "compare: Compare test")

# Session-scoped fixture
@pytest.fixture(scope="session")
def golden_data_dir():
    data_dir = Path(__file__).parent / "data"
    return data_dir

# Parametrize with custom IDs
@pytest.mark.parametrize(
    "song_dir",
    ["song_01", "song_02", ...],
    ids=lambda s: s  # Use song_dir as test ID
)
```

### 검증 결과
- ✅ 18개 테스트 수집 (smoke 10 + compare 8)
- ✅ compare 마커 필터링 동작 (8개)
- ✅ smoke 마커 여전히 동작 (10개)
- ✅ 기존 TestGoldenSmoke 100% 유지

### Docker 이슈
- Docker 볼륨 마운트 시 코드 변경이 즉시 반영되지 않음
- 해결: `docker compose down && docker compose up -d --build`로 재빌드 필요


## [2026-02-04] Task 4: Golden Test E2E Results

### Test Execution
- **Scope**: 8 Golden Songs (song_01 ~ song_08)
- **Tool**: Playwright MCP
- **Environment**: Local Docker (Frontend: :3000, Backend: :8000)

### Results
- **Success Rate**: 100% (8/8 songs processed)
- **Verification**:
  - All songs successfully uploaded
  - Processing completed (100% progress)
  - Result page displayed
  - MIDI download button confirmed visible
- **Evidence**: Screenshots saved in `.sisyphus/evidence/golden-e2e/`

### Observations
- Processing time varies but falls within 180s timeout.
- Frontend correctly handles file uploads and polling for status.
- "Download MIDI" button is a reliable indicator of success.
- Note: This test only verifies *availability* of output, not the *quality* of the MusicXML/MIDI content (which was noted as an issue in Task 3).
