# Reference MusicXML Structure Analysis

**Date**: 2026-02-04  
**Analyzed**: 8 reference.mxl files (song_01 ~ song_08)  
**Purpose**: Understand reference structure to enable melody extraction for comparison

---

## Executive Summary

All 8 reference files follow a **consistent piano arrangement structure**:
- **Single Part**: "피아노" (Piano) - full piano arrangement
- **Two Staves**: Staff 1 (right hand/melody) + Staff 2 (left hand/bass)
- **Two Primary Voices**: Voice 1 (melody) + Voice 5 (accompaniment)
- **Rich Harmonic Content**: Extensive use of chords (25-41% of notes are chord members)

**Key Finding**: Reference files contain **full piano arrangements**, not just melody. To compare with Basic Pitch output (melody only), we must **extract melody from Staff 1 / Voice 1**.

---

## Detailed Analysis by Song

### Song 01
- **Measures**: 97
- **Voices**: 1, 2, 5 (Voice 2 is rare, only 8 notes)
- **Total Notes**: 2,082 (1,543 individual notes + 539 chord notes)
- **Note Density**: 21.46 notes/measure
- **Octave Range**: 1-6
- **Staff Distribution**: Staff 1 (1,083 notes), Staff 2 (1,012 notes)

### Song 02
- **Measures**: 80
- **Voices**: 1, 5
- **Total Notes**: 1,739 (1,326 individual + 413 chord notes)
- **Note Density**: 21.74 notes/measure
- **Octave Range**: 1-7
- **Staff Distribution**: Staff 1 (870 notes), Staff 2 (880 notes)

### Song 03
- **Measures**: 119
- **Voices**: 1, 2, 5
- **Total Notes**: 1,724 (1,019 individual + 705 chord notes)
- **Note Density**: 14.49 notes/measure
- **Octave Range**: 1-6
- **Staff Distribution**: Staff 1 (793 notes), Staff 2 (933 notes)

### Song 04
- **Measures**: 129
- **Voices**: 1, 5
- **Total Notes**: 1,617 (1,213 individual + 404 chord notes)
- **Note Density**: 12.53 notes/measure
- **Octave Range**: 2-6
- **Staff Distribution**: Staff 1 (850 notes), Staff 2 (768 notes)

### Song 05
- **Measures**: 65
- **Voices**: 1, 5
- **Total Notes**: 1,403 (1,049 individual + 354 chord notes)
- **Note Density**: 21.58 notes/measure
- **Octave Range**: 1-5
- **Staff Distribution**: Staff 1 (746 notes), Staff 2 (664 notes)

### Song 06
- **Measures**: 94
- **Voices**: 1, 5
- **Total Notes**: 1,849 (1,315 individual + 534 chord notes)
- **Note Density**: 19.67 notes/measure
- **Octave Range**: 1-5
- **Staff Distribution**: Staff 1 (1,109 notes), Staff 2 (741 notes)

### Song 07
- **Measures**: 109
- **Voices**: 1, 5
- **Total Notes**: 1,694 (1,010 individual + 684 chord notes)
- **Note Density**: 15.54 notes/measure
- **Octave Range**: 1-6
- **Staff Distribution**: Staff 1 (875 notes), Staff 2 (820 notes)

### Song 08
- **Measures**: 142
- **Voices**: 1, 5
- **Total Notes**: 1,680 (1,321 individual + 359 chord notes)
- **Note Density**: 11.83 notes/measure
- **Octave Range**: 1-5
- **Staff Distribution**: Staff 1 (847 notes), Staff 2 (834 notes)

---

## Structure Patterns

### Part Structure
```
<score-partwise>
  <part-list>
    <score-part id="P1">
      <part-name>피아노</part-name>
      <part-abbreviation>Pno.</part-abbreviation>
    </score-part>
  </part-list>
  <part id="P1">
    <!-- All measures here -->
  </part>
</score-partwise>
```

**Observation**: All songs use a single part (P1) containing both staves.

### Voice Structure

**Voice 1** (Melody - Right Hand):
```xml
<note>
  <pitch><step>A</step><octave>4</octave></pitch>
  <duration>6</duration>
  <voice>1</voice>
  <staff>1</staff>
  <stem>up</stem>
</note>
```

**Voice 5** (Bass/Accompaniment - Left Hand):
```xml
<note>
  <pitch><step>C</step><octave>2</octave></pitch>
  <duration>6</duration>
  <voice>5</voice>
  <staff>2</staff>
  <stem>up</stem>
</note>
```

**Voice 2** (Rare - Additional melodic line):
- Only appears in Song 01 (8 notes) and Song 03
- Also on Staff 1
- Used for polyphonic passages

### Chord Representation

Chords are represented as multiple `<note>` elements with `<chord/>` marker:
```xml
<note>
  <pitch><step>C</step><octave>4</octave></pitch>
  <voice>1</voice>
  <staff>1</staff>
</note>
<note>
  <chord/>  <!-- This note is part of the previous chord -->
  <pitch><step>E</step><octave>4</octave></pitch>
  <voice>1</voice>
  <staff>1</staff>
</note>
<note>
  <chord/>
  <pitch><step>G</step><octave>4</octave></pitch>
  <voice>1</voice>
  <staff>1</staff>
</note>
```

**Chord Statistics**:
- Song 01: 25.9% chord notes (539/2082)
- Song 02: 23.7% chord notes (413/1739)
- Song 03: **40.9% chord notes** (705/1724) - highest
- Song 04: 25.0% chord notes (404/1617)
- Song 05: 25.2% chord notes (354/1403)
- Song 06: 28.9% chord notes (534/1849)
- Song 07: **40.4% chord notes** (684/1694)
- Song 08: 21.4% chord notes (359/1680) - lowest

---

## Melody Identification Criteria

Based on the analysis, **melody can be identified by**:

### Primary Criteria
1. **Staff Number**: `<staff>1</staff>` (right hand)
2. **Voice Number**: `<voice>1</voice>` (primary melodic voice)

### Secondary Criteria (for validation)
3. **Pitch Range**: Higher octaves (typically 3-6)
4. **Note Density**: Higher density than bass line
5. **Stem Direction**: Often `<stem>up</stem>` (though not always)

### Extraction Strategy

**Recommended approach**:
```python
def extract_melody_from_reference(score):
    """Extract melody from reference MusicXML"""
    melody_notes = []
    
    for part in score.parts:
        for element in part.flatten().notes:
            # Skip chord symbols
            if isinstance(element, music21.harmony.ChordSymbol):
                continue
            
            # Check if note belongs to melody voice
            # In MusicXML, voice is stored in note.voice
            if hasattr(element, 'voice') and element.voice == 1:
                # This is a melody note
                if isinstance(element, music21.note.Note):
                    melody_notes.append(element)
                elif isinstance(element, music21.chord.Chord):
                    # For chords in melody, take highest note
                    melody_notes.append(element.pitches[-1])
    
    return melody_notes
```

**Alternative approach** (if voice info is unreliable):
```python
def extract_melody_by_staff(musicxml_path):
    """Extract melody using staff number"""
    score = music21.converter.parse(musicxml_path)
    
    # Get all notes from staff 1
    staff1_notes = []
    for part in score.parts:
        for measure in part.getElementsByClass(music21.stream.Measure):
            for note in measure.flatten().notes:
                if hasattr(note, 'staff') and note.staff == 1:
                    staff1_notes.append(note)
    
    return staff1_notes
```

---

## Implications for Comparison

### Current Problem
- **Reference**: Full piano arrangement (melody + harmony + bass)
- **Generated**: Melody only (Basic Pitch output)
- **Current comparison**: Compares ALL reference notes vs melody → very low similarity (0.05-0.33%)

### Solution
**Extract melody from reference before comparison**:

1. Parse reference.mxl
2. Filter notes by `voice == 1` or `staff == 1`
3. Handle chords (take highest note or all notes depending on strategy)
4. Compare extracted melody vs generated melody

### Expected Improvement
- Current similarity: 0.05-0.33% (comparing full arrangement vs melody)
- Expected similarity after fix: **60-85%** (comparing melody vs melody)

---

## Technical Notes

### File Format
- **Extension**: `.mxl` (compressed MusicXML)
- **Structure**: ZIP archive containing:
  - `META-INF/container.xml` (metadata)
  - `score.xml` (actual MusicXML content)

### Extraction Command
```bash
unzip -q reference.mxl
# Extracts score.xml
```

### Voice Numbering Convention
- **Voice 1**: Primary melody (right hand, staff 1)
- **Voice 2**: Secondary melody (rare, staff 1)
- **Voice 5**: Bass/accompaniment (left hand, staff 2)

**Note**: Voice numbering is not sequential (1, 2, 5) - this is a MuseScore convention.

### Staff Numbering
- **Staff 1**: Treble clef (right hand) - higher pitches
- **Staff 2**: Bass clef (left hand) - lower pitches

---

## Recommendations

### For Wave 1 (Current)
1. ✅ **Implement melody extraction** from reference files
2. ✅ **Filter by voice=1** as primary method
3. ✅ **Handle chords** in melody (take highest note)
4. ✅ **Update comparison logic** to use extracted melody

### For Future Improvements
1. **Validate extraction**: Manually verify extracted melody sounds correct
2. **Handle polyphony**: Decide how to handle Voice 2 (ignore or include)
3. **Chord strategy**: Experiment with different chord handling (highest note vs all notes)
4. **Alignment**: Consider time-based alignment before note matching

---

## Appendix: Raw Data Summary

| Song | Measures | Voices | Total Notes | Individual | Chords | Density | Octaves | Staff1 | Staff2 |
|------|----------|--------|-------------|------------|--------|---------|---------|--------|--------|
| 01   | 97       | 1,2,5  | 2082        | 1543       | 539    | 21.46   | 1-6     | 1083   | 1012   |
| 02   | 80       | 1,5    | 1739        | 1326       | 413    | 21.74   | 1-7     | 870    | 880    |
| 03   | 119      | 1,2,5  | 1724        | 1019       | 705    | 14.49   | 1-6     | 793    | 933    |
| 04   | 129      | 1,5    | 1617        | 1213       | 404    | 12.53   | 2-6     | 850    | 768    |
| 05   | 65       | 1,5    | 1403        | 1049       | 354    | 21.58   | 1-5     | 746    | 664    |
| 06   | 94       | 1,5    | 1849        | 1315       | 534    | 19.67   | 1-5     | 1109   | 741    |
| 07   | 109      | 1,5    | 1694        | 1010       | 684    | 15.54   | 1-6     | 875    | 820    |
| 08   | 142      | 1,5    | 1680        | 1321       | 359    | 11.83   | 1-5     | 847    | 834    |

**Total**: 835 measures, 13,788 notes analyzed across 8 songs.
