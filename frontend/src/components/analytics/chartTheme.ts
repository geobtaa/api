/** Shared presentation for analytics time-series charts. */
export const chartTheme = {
  tick: {
    fill: '#6B7280',
    fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
    fontSize: 11,
    fontWeight: 500,
  },
  series: { stroke: '#2563EB', strokeWidth: 3 },
  fill: { color: '#2563EB', startOpacity: 0.24, endOpacity: 0 },
  grid: { stroke: '#E5E7EB', strokeDasharray: '2 6', vertical: false },
  cursor: { stroke: '#2563EB', strokeDasharray: '3 3' },
  tooltip: {
    background: '#FFFFFF',
    fontFamily: 'Inter, ui-sans-serif, system-ui, sans-serif',
    fontSize: 12,
    border: '1px solid #D1D5DB',
    borderRadius: 8,
    color: '#111827',
  },
  tooltipLabel: { color: '#111827', fontWeight: 600 },
};
