# Music21 Library Research for MusicXML Comparison

## Summary

Comprehensive research on music21's capabilities for MusicXML/MXL parsing, note extraction, comparison algorithms, and similarity metrics.

## 1. Parsing MXL/MusicXML Files

### Official Documentation Source
- **Documentation**: https://www.music21.org/music21docs/usersGuide/usersGuide_08_installingMusicXML.html
- **Latest commit**: be4d32da (Feb 4, 2026)

### Key Functions

**`music21.converter.parse()`** - Primary function for parsing MusicXML files
- Supports both `.xml`, `.musicxml`, and `.mxl` extensions
- `.mxl` files are compressed MusicXML archives (zip format)
- Can parse from local file paths or URLs
- Returns a `Score`, `Part`, or `Opus` object depending on file contents

```python
from music21 import converter

# Parse local file
c = converter.parse('/path/to/music.xml')
c = converter.parse('/path/to/music.mxl')

# Parse from URL
url = 'https://kern.humdrum.org/cgi-bin/ksdata?l=cc/bach/cello&file=bwv1007-01.krn&f=xml'
sAlt = converter.parse(url)

# Force re-parsing (skip cache)
c = converter.parse('file.xml', forceSource=True)
```

### MXL Archive Handling

**`music21.converter.ArchiveManager`** - For working with .mxl compressed archives
- `isArchive()` - Check if file is an archive
- `getNames()` - List contents of archive
- `getData()` - Extract data from archive

```python
fnCorpus = corpus.getWork('bwv66.6', fileExtensions=('.xml',))
am = converter.ArchiveManager(fnCorpus)
am.isArchive()  # True
am.getNames()  # ['bwv66.6.xml', 'META-INF/container.xml']
data = am.getData()
```

### Performance Optimization
- First parse is slower (2-5x)
- Subsequent parses use cached pickle files
- Use `forceSource=True` to bypass cache

## 2. Extracting Notes from Streams

### Stream Iteration

**`Stream.iter()`** - Create StreamIterator for efficient iteration

```python
s = converter.parse('file.xml')
sIter = s.iter()

# Standard iteration
for note in s:
    print(note, note.quarterLength)
```

### Filtering Elements

**Class Filters** - Filter by element type
```python
from music21.stream import filters

# Get only notes
noteFilter = filters.ClassFilter('Note')
noteIterator = s.iter().addFilter(noteFilter)

for note in noteIterator:
    print(note)
```

**Offset Filters** - Filter by time position
```python
offsetFilter = filters.OffsetFilter(offsetStart=0.5, offsetEnd=4.0)
offsetIterator = s.iter().addFilter(offsetFilter)
```

**Filter Shortcuts**
```python
# Chained filters
for note in s.iter().getElementsByClass('Note').getElementsByOffset(0.5, 4.0):
    print(note)
```

### Note Properties for Comparison

**`music21.note.Note`** - Core note class with comparison support

**Key Properties:**
- `name` - Note name (e.g., 'C', 'D#', 'B-')
- `nameWithOctave` - Note with octave (e.g., 'C4', 'D#5')
- `octave` - Octave number (e.g., 4, 5)
- `pitch` - Pitch object (contains `pitchClass`, `midi`, etc.)
- `quarterLength` - Duration in quarter notes
- `duration` - Duration object
- `pitch.pitchClass` - Integer 0-11 (pitch class ignoring octave)

**Equality Comparison:**
```python
from music21 import note

# Exact match (same pitch and duration)
note.Note('C4') == note.Note('C4')  # True
note.Note('C4') == note.Note('C4', type='half')  # False (different duration)

# Enharmonics are NOT equal
note.Note('D#4') == note.Note('E-4')  # False

# Ordering by pitch
note.Note('E5') > note.Note('F2')  # True (higher pitch)
```

**Important Note**: Enharmonic notes (different spellings of same pitch like D#/E-) are NOT considered equal.

## 3. Note Comparison Algorithms

### music21.search.base Module

**Source**: https://github.com/cuthbertlab/music21/blob/be4d32da/music21/search/base.py

### `approximateNoteSearch()` - Fuzzy Note Matching

Searches for approximate matches considering both pitch and rhythm.

**Evidence** ([source](https://github.com/cuthbertlab/music21/blob/be4d32da/music21/search/base.py#L514-L540)):
```python
from music21 import converter, search

s = converter.parse("tinynotation: 4/4 c4 d8 e16 FF a'4 b-")
o1 = converter.parse("tinynotation: 4/4 c4 d8 e GG a' b-4")
o2 = converter.parse("tinynotation: 4/4 d#2 f A a' G b")

l = search.approximateNoteSearch(s, [o1, o2])
for match in l:
    print(f'{match.id} {match.matchProbability!r}')
# Output:
# o1 0.6666...
# o3 0.3333...
# o2 0.0833...
```

**Returns**: Ordered list of streams with `matchProbability` attribute (0.0 to 1.0)

**Implementation**: Uses `difflib.SequenceMatcher.ratio()` on string representations of streams

### `approximateNoteSearchNoRhythm()` - Pitch-Only Comparison

Ignores rhythm, compares only pitch content.

### `approximateNoteSearchOnlyRhythm()` - Rhythm-Only Comparison

Ignores pitch, compares only duration/rhythm patterns.

### `approximateNoteSearchWeighted()` - Weighted Comparison

Allows custom weighting of pitch vs rhythm factors.

### `StreamSearcher` Class - Advanced Pattern Matching

**Evidence** ([source](https://github.com/cuthbertlab/music21/blob/be4d32da/music21/search/base.py#L108-L180)):
```python
from music21.search import StreamSearcher
from music21 import note

thisStream = converter.parse('tinynotation: 3/4 c4. d8 e4 g4. a8 f4. c4. d4')
searchList = [note.Note('C', quarterLength=1.5), note.Note('D', quarterLength=0.5)]

ss = StreamSearcher(thisStream, searchList)
ss.recurse = True
ss.filterNotes = True

# Add algorithms
ss.algorithms.append(StreamSearcher.rhythmAlgorithm)

results = ss.run()
for match in results:
    print(f'Measure {match.elStart.measureNumber}: {match.els}')
```

**Built-in Algorithms:**
- `wildcardAlgorithm()` - Wildcard pattern matching (default)
- `rhythmAlgorithm()` - Duration comparison
- `noteNameAlgorithm()` - Note name comparison

**Custom Algorithms:**
```python
# Define custom pitch class comparison
def pitchClassEqual(n1, n2):
    if n1.pitch.pitchClass == n2.pitch.pitchClass:
        return True
    else:
        return False

search.streamSearchBase(stream, searchList, algorithm=pitchClassEqual)
```

### Stream Translation for Comparison

**`translateStreamToString()`** - Convert stream to searchable string
- Encodes notes to character representations
- Includes pitch, duration, and tie information

**`translateStreamToStringNoRhythm()`** - Pitch-only representation

**`translateStreamToStringOnlyRhythm()`** - Rhythm-only representation

```python
from music21 import search

# Get string representation for comparison
s = converter.parse('file.xml')
n = s.flatten().notesAndRests
streamStr = search.translateStreamToString(n)
print(streamStr)  # e.g., 'NNJLNOLLLJJIJLLLLNJJJIJLLJNNJL'
```

## 4. Similarity Metrics

### music21.search.segment Module

**Source**: https://github.com/cuthbertlab/music21/blob/be4d32da/music21/search/segment.py

### `scoreSimilarity()` - Multi-Score Similarity Analysis

**Evidence** ([source](https://github.com/cuthbertlab/music21/blob/be4d32da/music21/search/segment.py#L296-L360)):
```python
from music21 import converter, corpus, search

# Index multiple scores
filePaths = []
for p in ('bwv197.5.mxl', 'bwv190.7.mxl', 'bwv197.10.mxl'):
    source = corpus.search(p)[0].sourcePath
    filePaths.append(source)

scoreDict = search.segment.indexScoreFilePaths(filePaths)
scoreSim = search.segment.scoreSimilarity(scoreDict)
print(len(scoreSim))  # 496 similarity tuples

# Sample results:
# ('bwv197.5.mxl', 1, 1, (4, 10), 'bwv190.7.mxl', 3, 4, (22, 30), 0.13...)
# ('bwv197.5.mxl', 1, 1, (4, 10), 'bwv197.10.mxl', 0, 0, (0, 8), 0.2)
```

**Returns**: List of tuples with:
- Score 1 name, voice number, measure range
- Score 2 name, voice number, measure range
- Similarity score (0.0 to 1.0)

**Parameters:**
- `minimumLength=20` - Minimum segment length to compare
- `giveUpdates=False` - Progress updates
- `includeReverse=False` - Include reverse comparisons
- `forceDifflib=False` - Force use of difflib instead of python-Levenshtein

### Similarity Algorithm Implementation

**Uses Levenshtein/SequenceMatcher distance**:
```python
# From music21/search/segment.py#L340-L344
def getDifflibOrPyLev(seq1, seq2, 
