import {
  publishedMonths,
  monthLabel,
  comparisonLabel,
} from '../../config/analyticsPeriods';
import { CalendarDays } from 'lucide-react';

export function ReportingPeriodPicker({
  id,
  value,
  onChange,
  label = 'Reporting month',
  comparison = false,
  includeThreeMonths = false,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  label?: string;
  comparison?: boolean;
  includeThreeMonths?: boolean;
}) {
  return (
    <div className="analytics-month-picker">
      <CalendarDays className="h-4 w-4" aria-hidden />
      <label htmlFor={id} className="sr-only">
        {comparison ? 'Comparison period' : label}
      </label>
      <select
        id={id}
        aria-label={comparison ? 'Comparison period' : label}
        value={comparison ? 'comparison' : value}
        disabled={comparison}
        onChange={(event) => onChange(event.target.value)}
      >
        {comparison ? (
          <option value="comparison">{comparisonLabel}</option>
        ) : (
          <>
            {includeThreeMonths && (
              <option value="3months">Past 3 months</option>
            )}
            {[...publishedMonths].reverse().map((month) => (
              <option key={month} value={month}>
                {monthLabel(month)}
              </option>
            ))}
            <option value="all">All time (since July 1)</option>
          </>
        )}
      </select>
    </div>
  );
}
