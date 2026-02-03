/**
 * Convert seconds to mm:ss.s format
 * @param seconds - Time in seconds (e.g., 90.5)
 * @returns Formatted time string (e.g., "01:30.5")
 */
export function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins.toString().padStart(2, '0')}:${secs.padStart(4, '0')}`;
}

/**
 * Parse mm:ss.s format to seconds
 * @param timeStr - Time string (e.g., "01:30.5")
 * @returns Time in seconds (e.g., 90.5)
 */
export function parseTime(timeStr: string): number {
  const parts = timeStr.split(':');
  if (parts.length !== 2) {
    throw new Error('Invalid time format. Expected mm:ss.s');
  }
  
  const mins = parseInt(parts[0], 10);
  const secs = parseFloat(parts[1]);
  
  if (isNaN(mins) || isNaN(secs)) {
    throw new Error('Invalid time values');
  }
  
  return mins * 60 + secs;
}

/**
 * Validate time string format
 * @param timeStr - Time string to validate
 * @returns true if valid, false otherwise
 */
export function isValidTimeFormat(timeStr: string): boolean {
  const pattern = /^\d{1,2}:\d{1,2}(\.\d)?$/;
  if (!pattern.test(timeStr)) return false;
  
  try {
    const seconds = parseTime(timeStr);
    return seconds >= 0;
  } catch {
    return false;
  }
}
