import { CalendarDays } from 'lucide-react';

export function ReportingPeriodPicker({
  id,
  value,
  onChange,
  label = 'Reporting month',
  comparison = false,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  label?: string;
  comparison?: boolean;
}) {
  return (
    <div className="analytics-month-picker">
      <CalendarDays className="h-4 w-4" aria-hidden />
      <label htmlFor={id} className="sr-only">
        {comparison ? 'Comparison period' : label}
      </label>
      <select
        id={id}
        value={comparison ? 'comparison' : value}
        disabled={comparison}
        onChange={(event) => onChange(event.target.value)}
      >
        {comparison ? (
          <option value="comparison">July–August 2026</option>
        ) : (
          <>
            <option value="2026-08">August 2026</option>
            <option value="2026-07">July 2026</option>
            <option value="all">All time (since July 1)</option>
          </>
        )}
      </select>
    </div>
  );
}
