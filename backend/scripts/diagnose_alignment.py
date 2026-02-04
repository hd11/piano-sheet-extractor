#!/usr/bin/env python3
"""Golden compare alignment diagnostic (DIAGNOSTIC ONLY).

What it does (for one song, default song_01):
- Runs the same pipeline as golden compare to produce sheet_medium.musicxml
- Parses reference.mxl and the generated sheet with music21
- Prints first N notes (pitch, onset_ql, dur_ql) for each
- Reports onset deltas (ql + seconds) for closest same-pitch candidates

Run:
  backend/.venv/Scripts/python.exe backend/scripts/diagnose_alignment.py --song song_01 --n 10
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Iterable, Optional

import music21

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from core.audio_to_midi import convert_audio_to_midi
from core.audio_analysis import analyze_audio
from core.difficulty_adjuster import generate_all_sheets
from core.melody_extractor import extract_melody
from core.midi_to_musicxml import quarter_length_to_seconds


@dataclass(frozen=True)
class N:
    pitch: int
    onset_ql: float
    dur_ql: float


def bpm_from_score(score: music21.stream.Score) -> Optional[float]:
    for mm in score.flatten().getElementsByClass(music21.tempo.MetronomeMark):
        if mm.number is None:
            continue
        try:
            return float(mm.number)
        except Exception:
            pass
    return None


def extract_notes(score: music21.stream.Score) -> list[N]:
    out: list[N] = []
    for el in score.flatten().notes:
        if isinstance(el, music21.note.Note):
            out.append(N(el.pitch.midi, float(el.offset), float(el.duration.quarterLength)))
        elif isinstance(el, music21.chord.Chord):
            for p in el.pitches:
                out.append(N(p.midi, float(el.offset), float(el.duration.quarterLength)))
    out.sort(key=lambda x: (x.onset_ql, x.pitch))
    return out


def span_ql(notes: list[N]) -> float:
    return max((n.onset_ql + n.dur_ql for n in notes), default=0.0)


def pitch_range(notes: list[N]) -> str:
    if not notes:
        return "-"
    ps = [n.pitch for n in notes]
    return f"{min(ps)}..{max(ps)}"


def fmt(n: Optional[N]) -> str:
    if n is None:
        return "-"
    return f"p={n.pitch:3d} t={n.onset_ql:8.3f} d={n.dur_ql:6.3f}"


def closest_same_pitch(ref: N, gen: list[N], limit: int = 20000) -> Optional[N]:
    best = None
    best_diff = None
    for g in gen[: min(len(gen), limit)]:
        if g.pitch != ref.pitch:
            continue
        diff = abs(g.onset_ql - ref.onset_ql)
        if best_diff is None or diff < best_diff:
            best, best_diff = g, diff
    return best


def ql_to_s(ql: float, bpm: float) -> float:
    return quarter_length_to_seconds(ql, bpm)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--song", default="song_01")
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    song_dir = BACKEND_DIR / "tests" / "golden" / "data" / args.song
    ref_path = song_dir / "reference.mxl"
    mp3_path = song_dir / "input.mp3"

    if not ref_path.exists():
        raise SystemExit(f"Missing reference: {ref_path}")
    if not mp3_path.exists():
        raise SystemExit(f"Missing input mp3: {mp3_path}")

    out_dir = BACKEND_DIR / "scripts" / "_diagnose_out" / args.song
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print(f"song={args.song}")
    print(f"reference={ref_path}")
    print(f"input={mp3_path}")
    print(f"out_dir={out_dir}")
    print("=" * 88)

    # 1) Produce generated sheet_medium.musicxml via the pipeline.
    raw_midi = out_dir / "raw.mid"
    melody_midi = out_dir / "melody.mid"

    print("\n[1] pipeline: audio -> raw.mid")
    midi_meta = convert_audio_to_midi(mp3_path, raw_midi)
    print(f"  note_events={midi_meta.get('note_count')} duration_s={midi_meta.get('duration_seconds'):.2f}")

    print("\n[2] pipeline: raw.mid -> melody notes -> melody.mid")
    melody_notes = extract_melody(raw_midi)
    print(f"  melody_notes={len(melody_notes)}")

    import pretty_midi

    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    for n in melody_notes:
        inst.notes.append(
            pretty_midi.Note(
                velocity=int(n.velocity),
                pitch=int(n.pitch),
                start=float(n.onset),
                end=float(n.onset + n.duration),
            )
        )
    pm.instruments.append(inst)
    pm.write(str(melody_midi))

    print("\n[3] pipeline: analyze_audio -> generate sheet_medium.musicxml")
    analysis = analyze_audio(mp3_path)
    (out_dir / "analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    bpm_analysis = float(analysis.get("bpm") or 0.0)
    print(f"  bpm_analysis={bpm_analysis:.2f} conf={analysis.get('bpm_confidence')}")

    sheets = generate_all_sheets(out_dir, melody_midi, analysis)
    gen_path = sheets["medium"]
    print(f"  generated={gen_path} bytes={gen_path.stat().st_size}")

    # 2) Parse and compare.
    print("\n[4] parse both scores")
    ref_score = music21.converter.parse(str(ref_path))
    gen_score = music21.converter.parse(str(gen_path))

    bpm_ref = bpm_from_score(ref_score)
    bpm_gen = bpm_from_score(gen_score)

    ref_notes = extract_notes(ref_score)
    gen_notes = extract_notes(gen_score)

    print(f"  bpm_ref(from MXL)={bpm_ref}")
    print(f"  bpm_gen(from XML)={bpm_gen}")
    print(f"  ref_notes={len(ref_notes)} gen_notes={len(gen_notes)}")
    print(f"  ref_pitch_range={pitch_range(ref_notes[:2000])}")
    print(f"  gen_pitch_range={pitch_range(gen_notes[:2000])}")
    print(f"  ref_span_ql={span_ql(ref_notes):.3f}")
    print(f"  gen_span_ql={span_ql(gen_notes):.3f}")
    if ref_notes and gen_notes:
        print(f"  first_onset_ql ref={ref_notes[0].onset_ql:.3f} gen={gen_notes[0].onset_ql:.3f} delta={gen_notes[0].onset_ql - ref_notes[0].onset_ql:+.3f}")

    # 3) Print first N notes.
    n = args.n
    print("\n[5] first N notes (sorted by onset then pitch)")
    print("  idx | reference                     | generated")
    print("  ----+-------------------------------+-------------------------------")
    for i in range(n):
        r = ref_notes[i] if i < len(ref_notes) else None
        g = gen_notes[i] if i < len(gen_notes) else None
        print(f"  {i:3d} | {fmt(r):29s} | {fmt(g):29s}")

    # 4) Closest same-pitch onset deltas.
    print("\n[6] closest same-pitch for first N ref notes")
    print("  idx | ref(p,t) -> gen(t) | delta_ql | delta_s(using bpm_analysis)")
    print("  ----+--------------------+----------+---------------------------")

    deltas_ql: list[float] = []
    for i in range(min(n, len(ref_notes))):
        r = ref_notes[i]
        best = closest_same_pitch(r, gen_notes)
        if best is None:
            print(f"  {i:3d} | ref(p={r.pitch:3d},t={r.onset_ql:8.3f}) -> none")
            continue
        dql = best.onset_ql - r.onset_ql
        deltas_ql.append(dql)
        if bpm_analysis > 0:
            ds = ql_to_s(best.onset_ql, bpm_analysis) - ql_to_s(r.onset_ql, bpm_analysis)
            print(f"  {i:3d} | ref(p={r.pitch:3d},t={r.onset_ql:8.3f}) -> {best.onset_ql:8.3f} | {dql:+8.3f} | {ds:+9.3f}")
        else:
            print(f"  {i:3d} | ref(p={r.pitch:3d},t={r.onset_ql:8.3f}) -> {best.onset_ql:8.3f} | {dql:+8.3f}")

    if deltas_ql:
        print(f"\n  median delta_ql (closest same-pitch, first {len(deltas_ql)} notes) = {median(deltas_ql):+.3f}")

    # 5) Pitch overlap sanity.
    ref_p = {x.pitch for x in ref_notes}
    gen_p = {x.pitch for x in gen_notes}
    print("\n[7] pitch overlap (distinct pitches)")
    print(f"  ref_distinct={len(ref_p)} gen_distinct={len(gen_p)} overlap={len(ref_p & gen_p)}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
