"""
Basic Pitch + Skyline 알고리즘 테스트 스크립트

목적:
- Basic Pitch로 audio → MIDI 변환
- Skyline 알고리즘으로 멜로디 추출
- Reference MIDI와 비교

테스트 대상:
- song_01: 194.6s, reference 1,897 notes
"""

import time
from pathlib import Path
import sys

# Fix scipy.signal.gaussian compatibility issue
import scipy.signal

if not hasattr(scipy.signal, "gaussian"):
    from scipy.signal.windows import gaussian

    scipy.signal.gaussian = gaussian

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
from core.midi_parser import parse_midi, Note
from core.melody_extractor import (
    apply_skyline,
    filter_short_notes,
    resolve_overlaps,
    normalize_octave,
)


def analyze_notes(notes: list[Note]) -> dict:
    """Note 리스트 분석"""
    if not notes:
        return {
            "count": 0,
            "pitch_min": 0,
            "pitch_max": 0,
            "avg_duration": 0,
        }

    return {
        "count": len(notes),
        "pitch_min": min(n.pitch for n in notes),
        "pitch_max": max(n.pitch for n in notes),
        "avg_duration": sum(n.duration for n in notes) / len(notes),
    }


def test_basic_pitch(audio_path: Path, output_dir: Path):
    """Basic Pitch 테스트"""
    print(f"\n{'=' * 60}")
    print(f"Testing Basic Pitch on: {audio_path.name}")
    print(f"{'=' * 60}\n")

    # 1. Basic Pitch 실행
    print("Step 1: Running Basic Pitch...")
    start_time = time.time()

    model_output, midi_data, note_events = predict(
        str(audio_path),
        ICASSP_2022_MODEL_PATH,
    )

    elapsed = time.time() - start_time
    print(f"[OK] Basic Pitch completed in {elapsed:.1f}s")

    # 2. MIDI 저장
    output_midi = output_dir / "basic_pitch_raw.mid"
    output_midi.parent.mkdir(parents=True, exist_ok=True)
    midi_data.write(str(output_midi))
    print(f"[OK] Saved raw MIDI to: {output_midi}")

    # 3. Raw MIDI 분석
    raw_notes = parse_midi(output_midi)
    raw_stats = analyze_notes(raw_notes)
    print(f"\nRaw MIDI stats:")
    print(f"  Notes: {raw_stats['count']}")
    print(f"  Pitch range: {raw_stats['pitch_min']}-{raw_stats['pitch_max']}")
    print(f"  Avg duration: {raw_stats['avg_duration'] * 1000:.1f}ms")

    # 4. Skyline 적용
    print("\nStep 2: Applying Skyline algorithm...")
    skyline_notes = apply_skyline(raw_notes)
    skyline_stats = analyze_notes(skyline_notes)
    print(f"[OK] After Skyline: {skyline_stats['count']} notes")

    # 5. 짧은 음표 제거
    print("\nStep 3: Filtering short notes...")
    filtered_notes = filter_short_notes(skyline_notes)
    filtered_stats = analyze_notes(filtered_notes)
    print(f"[OK] After filtering: {filtered_stats['count']} notes")

    # 6. Overlap 해결
    print("\nStep 4: Resolving overlaps...")
    resolved_notes = resolve_overlaps(filtered_notes)
    resolved_stats = analyze_notes(resolved_notes)
    print(f"[OK] After overlap resolution: {resolved_stats['count']} notes")

    # 7. 옥타브 정규화
    print("\nStep 5: Normalizing octaves...")
    final_notes = normalize_octave(resolved_notes, min_pitch=48, max_pitch=84)
    final_stats = analyze_notes(final_notes)
    print(f"[OK] After normalization: {final_stats['count']} notes")

    # 8. 최종 MIDI 저장
    import pretty_midi

    output_melody = output_dir / "basic_pitch_melody.mid"
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano

    for note in final_notes:
        midi_note = pretty_midi.Note(
            velocity=note.velocity,
            pitch=note.pitch,
            start=note.onset,
            end=note.onset + note.duration,
        )
        inst.notes.append(midi_note)

    pm.instruments.append(inst)
    pm.write(str(output_melody))
    print(f"[OK] Saved melody MIDI to: {output_melody}")

    return {
        "elapsed": elapsed,
        "raw": raw_stats,
        "skyline": skyline_stats,
        "filtered": filtered_stats,
        "resolved": resolved_stats,
        "final": final_stats,
    }


def compare_with_reference(reference_path: Path):
    """Reference MIDI 분석"""
    print(f"\n{'=' * 60}")
    print(f"Reference MIDI: {reference_path.name}")
    print(f"{'=' * 60}\n")

    ref_notes = parse_midi(reference_path)
    ref_stats = analyze_notes(ref_notes)

    print(f"Reference stats:")
    print(f"  Notes: {ref_stats['count']}")
    print(f"  Pitch range: {ref_stats['pitch_min']}-{ref_stats['pitch_max']}")
    print(f"  Avg duration: {ref_stats['avg_duration'] * 1000:.1f}ms")

    return ref_stats


def main():
    # Paths
    audio_path = Path("backend/tests/golden/data/song_01/input.mp3")
    reference_path = Path("backend/tests/golden/data/song_01/reference.mid")
    output_dir = Path("backend/scripts/output")

    # Validate inputs
    if not audio_path.exists():
        print(f"ERROR: Audio file not found: {audio_path}")
        return

    if not reference_path.exists():
        print(f"ERROR: Reference MIDI not found: {reference_path}")
        return

    # Run tests
    ref_stats = compare_with_reference(reference_path)
    bp_results = test_basic_pitch(audio_path, output_dir)

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}\n")

    print(f"Reference MIDI: {ref_stats['count']} notes")
    print(f"Basic Pitch (raw): {bp_results['raw']['count']} notes")
    print(f"Basic Pitch + Skyline: {bp_results['final']['count']} notes")
    print(f"Processing time: {bp_results['elapsed']:.1f}s")

    # Ratio
    if ref_stats["count"] > 0:
        raw_ratio = (bp_results["raw"]["count"] / ref_stats["count"]) * 100
        final_ratio = (bp_results["final"]["count"] / ref_stats["count"]) * 100
        print(f"\nRatio vs Reference:")
        print(f"  Raw: {raw_ratio:.1f}%")
        print(f"  Final: {final_ratio:.1f}%")

    print(f"\n{'=' * 60}")
    print("Output files:")
    print(f"  {output_dir / 'basic_pitch_raw.mid'}")
    print(f"  {output_dir / 'basic_pitch_melody.mid'}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
