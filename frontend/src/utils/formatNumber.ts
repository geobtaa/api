/**
 * Formats a number with thousand separators (commas)
 * @param num - The number to format
 * @returns A formatted string with commas (e.g., 143691 -> "143,691")
 */
export function formatCount(num: number | string | undefined | null): string {
  if (num === null || num === undefined) {
    return '0';
  }

  const numValue = typeof num === 'string' ? parseInt(num, 10) : num;

  if (isNaN(numValue)) {
    return '0';
  }

  return numValue.toLocaleString('en-US');
}
