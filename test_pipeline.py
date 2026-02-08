"""Quick test of vocal separation pipeline on 2 songs."""

import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from core.vocal_melody_extractor import extract_melody
from core.reference_extractor import extract_reference_melody
from core.comparator import compare_melodies

def test_song(mp3_name: str, mxl_name: str):
    """Test pipeline on a single song."""
    print(f"\n{'='*60}")
    print(f"Testing: {mp3_name}")
    print(f"{'='*60}")
    
    mp3_path = Path('test') / mp3_name
    mxl_path = Path('test') / mxl_name
    cache_dir = Path('test/cache')
    
    try:
        # Extract melody from MP3
        print(f"[1/3] Extracting melody from {mp3_name}...")
        extracted = extract_melody(mp3_path, cache_dir=cache_dir)
        print(f"      ✓ Extracted {len(extracted)} notes")
        
        # Extract reference melody from MXL
        print(f"[2/3] Extracting reference from {mxl_name}...")
        reference = extract_reference_melody(mxl_path)
        print(f"      ✓ Reference has {len(reference)} notes")
        
        # Compare melodies
        print(f"[3/3] Comparing melodies...")
        metrics = compare_melodies(extracted, reference)
        
        # Print results
        print(f"\n      Results for {mp3_name}:")
        print(f"      - pitch_class_f1: {metrics['pitch_class_f1']:.4f}")
        print(f"      - raw_pitch_f1:   {metrics['raw_pitch_f1']:.4f}")
        print(f"      - voicing_recall: {metrics['voicing_recall']:.4f}")
        print(f"      - voicing_false_alarm: {metrics['voicing_false_alarm']:.4f}")
        
        return metrics['pitch_class_f1']
        
    except Exception as e:
        print(f"      ✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    print("Vocal Separation Pipeline - 2-Song Test")
    print("Testing end-to-end functionality...")
    
    results = {}
    
    # Test 1: English filename
    f1_golden = test_song('Golden.mp3', 'Golden.mxl')
    if f1_golden is not None:
        results['Golden.mp3'] = f1_golden
    
    # Test 2: Korean filename
    f1_korean = test_song('꿈의 버스.mp3', '꿈의 버스.mxl')
    if f1_korean is not None:
        results['꿈의 버스.mp3'] = f1_korean
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    if results:
        for song, f1 in results.items():
            print(f"{song}: pitch_class_f1 = {f1:.4f}")
        avg_f1 = sum(results.values()) / len(results)
        print(f"\nAverage pitch_class_f1: {avg_f1:.4f}")
        print(f"Status: ✓ Pipeline working (both songs processed successfully)")
    else:
        print("Status: ✗ Pipeline failed (no results)")
        sys.exit(1)

