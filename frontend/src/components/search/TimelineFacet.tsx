import React, { useEffect, useMemo } from 'react';
import {
  BarChart,
  Bar,
  Cell,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
  XAxis,
} from 'recharts';

/** When there are more than this many years, show decade buckets so bars stay visible. */
const BUCKET_THRESHOLD = 50;
const DECADE_SIZE = 10;
const MIN_YEAR = 1000;
const MAX_YEAR = 2030;
const YEAR_INPUT_PATTERN = /^\d{4}$/;

type TimelineFacetItem =
  | [value: string | number, hits: number]
  | {
      attributes: {
        value: string | number;
        hits: number;
      };
    };

type TimelineFacetData = {
  type?: string;
  id?: string;
  attributes: {
    label?: string;
    items: TimelineFacetItem[];
  };
};

export type SelectedYearRange = {
  start: number | null;
  end: number | null;
};

interface TimelineFacetProps {
  facet: TimelineFacetData;
  selectedRange: SelectedYearRange | null;
  onChange: (range: SelectedYearRange | null) => void;
}

type YearCount = {
  year: number;
  count: number;
};

/** One point on the chart: either a single year (raw) or a decade bucket. */
type ChartPoint = {
  xKey: number;
  xEnd: number;
  count: number;
  label: string;
};

export function TimelineFacet({
  facet,
  selectedRange,
  onChange,
}: TimelineFacetProps) {
  const [state, setState] = React.useState<{
    refAreaLeft?: number | string;
    refAreaRight?: number | string;
    isDragging: boolean;
  }>({ isDragging: false });
  const [manualStartYear, setManualStartYear] = React.useState('');
  const [manualEndYear, setManualEndYear] = React.useState('');
  const [manualError, setManualError] = React.useState<string | null>(null);
  const [hoveredKey, setHoveredKey] = React.useState<number | null>(null);

  // Process data: raw years, or decade buckets when there are too many years
  const { data, isBucketed } = useMemo(() => {
    if (!facet.attributes.items || facet.attributes.items.length === 0)
      return { data: [], isBucketed: false };

    const items: YearCount[] = facet.attributes.items
      .map((item) => {
        if (Array.isArray(item)) {
          return {
            year: Number(item[0]),
            count: Number(item[1]),
          };
        } else {
          return {
            year: Number(item.attributes.value),
            count: Number(item.attributes.hits),
          };
        }
      })
      .filter((d) => d.year >= MIN_YEAR && d.year <= MAX_YEAR);

    const sorted = items.sort((a, b) => a.year - b.year);
    if (sorted.length <= BUCKET_THRESHOLD) {
      const data: ChartPoint[] = sorted.map((d) => ({
        xKey: d.year,
        xEnd: d.year,
        count: d.count,
        label: String(d.year),
      }));
      return { data, isBucketed: false };
    }

    // Aggregate by decade so bars stay visible
    const byDecade = new Map<number, number>();
    for (const d of sorted) {
      const start = Math.floor(d.year / DECADE_SIZE) * DECADE_SIZE;
      byDecade.set(start, (byDecade.get(start) ?? 0) + d.count);
    }
    const data: ChartPoint[] = Array.from(byDecade.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([start]) => ({
        xKey: start,
        xEnd: start + DECADE_SIZE - 1,
        count: byDecade.get(start) ?? 0,
        label: `${start}s`,
      }));
    return { data, isBucketed: true };
  }, [facet]);

  const availableStartYear = data[0]?.xKey ?? null;
  const availableEndYear = data[data.length - 1]?.xEnd ?? null;

  useEffect(() => {
    setManualStartYear(
      selectedRange?.start != null
        ? String(selectedRange.start)
        : selectedRange
          ? ''
          : availableStartYear != null
            ? String(availableStartYear)
            : ''
    );
    setManualEndYear(
      selectedRange?.end != null
        ? String(selectedRange.end)
        : selectedRange
          ? ''
          : availableEndYear != null
            ? String(availableEndYear)
            : ''
    );
    setManualError(null);
  }, [availableEndYear, availableStartYear, selectedRange]);

  if (data.length === 0) return null;

  const selectPoint = (point: ChartPoint) => {
    onChange({ start: point.xKey, end: point.xEnd });
  };

  const onMouseDown = (e: any) => {
    if (e && e.activeLabel) {
      setState((prev) => ({
        ...prev,
        refAreaLeft: e.activeLabel,
        isDragging: true,
      }));
    }
  };

  const onMouseMove = (e: any) => {
    if (state.isDragging && e && e.activeLabel) {
      setState((prev) => ({ ...prev, refAreaRight: e.activeLabel }));
    }
  };

  const onMouseUp = () => {
    if (state.isDragging) {
      setState({
        ...state,
        isDragging: false,
        refAreaLeft: undefined,
        refAreaRight: undefined,
      });

      if (
        !state.refAreaLeft ||
        !state.refAreaRight ||
        state.refAreaLeft === state.refAreaRight
      ) {
        const clickedKey = Number(state.refAreaRight ?? state.refAreaLeft);
        const clickedPoint = data.find((p) => p.xKey === clickedKey);
        if (clickedPoint) selectPoint(clickedPoint);
        return;
      }

      let leftKey = Number(state.refAreaLeft);
      let rightKey = Number(state.refAreaRight);
      if (leftKey > rightKey) [leftKey, rightKey] = [rightKey, leftKey];

      if (isBucketed) {
        const rightPoint = data.find((p) => p.xKey === rightKey);
        const rightEnd = rightPoint
          ? rightPoint.xEnd
          : rightKey + DECADE_SIZE - 1;
        onChange({ start: leftKey, end: rightEnd });
      } else {
        onChange({ start: leftKey, end: rightKey });
      }
    }
  };

  const onChartClick = (e: any) => {
    if (!e?.activeLabel || state.isDragging) return;
    const point = data.find((p) => p.xKey === Number(e.activeLabel));
    if (point) selectPoint(point);
  };

  const startYear = selectedRange?.start ?? null;
  const endYear = selectedRange?.end ?? null;

  const handleManualYearChange =
    (setter: React.Dispatch<React.SetStateAction<string>>) =>
    (event: React.ChangeEvent<HTMLInputElement>) => {
      setter(event.target.value.replace(/\D/g, '').slice(0, 4));
      if (manualError) setManualError(null);
    };

  const handleManualSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!manualStartYear && !manualEndYear) {
      setManualError('Enter a start year, an end year, or both.');
      return;
    }

    if (
      (manualStartYear && !YEAR_INPUT_PATTERN.test(manualStartYear)) ||
      (manualEndYear && !YEAR_INPUT_PATTERN.test(manualEndYear))
    ) {
      setManualError('Enter years as 4-digit numbers.');
      return;
    }

    const parsedStartYear = manualStartYear ? Number(manualStartYear) : null;
    const parsedEndYear = manualEndYear ? Number(manualEndYear) : null;
    if (
      (parsedStartYear != null &&
        (parsedStartYear < MIN_YEAR || parsedStartYear > MAX_YEAR)) ||
      (parsedEndYear != null &&
        (parsedEndYear < MIN_YEAR || parsedEndYear > MAX_YEAR))
    ) {
      setManualError(`Enter years between ${MIN_YEAR} and ${MAX_YEAR}.`);
      return;
    }

    let normalizedRange: SelectedYearRange = {
      start: parsedStartYear,
      end: parsedEndYear,
    };

    if (
      parsedStartYear != null &&
      parsedEndYear != null &&
      parsedStartYear > parsedEndYear
    ) {
      normalizedRange = {
        start: parsedEndYear,
        end: parsedStartYear,
      };
    }

    setManualError(null);
    onChange(normalizedRange);
  };

  const handleClear = () => {
    setManualStartYear('');
    setManualEndYear('');
    setManualError(null);
    onChange(null);
  };

  const refAreaX1 = selectedRange
    ? selectedRange.start == null
      ? null
      : isBucketed
        ? Math.floor(selectedRange.start / DECADE_SIZE) * DECADE_SIZE
        : selectedRange.start
    : null;
  const refAreaX2 = selectedRange
    ? selectedRange.end == null
      ? null
      : isBucketed
        ? Math.floor(selectedRange.end / DECADE_SIZE) * DECADE_SIZE
        : selectedRange.end
    : null;

  const selectedRangeLabel =
    startYear != null && endYear != null
      ? `${startYear} - ${endYear}`
      : startYear != null
        ? `${startYear}+`
        : endYear != null
          ? `Up to ${endYear}`
          : 'All Years';
  const isPointSelected = (point: ChartPoint) => {
    if (!selectedRange) return false;
    const selectedStart = selectedRange.start ?? availableStartYear;
    const selectedEnd = selectedRange.end ?? availableEndYear;
    if (selectedStart == null || selectedEnd == null) return false;
    return point.xKey <= selectedEnd && point.xEnd >= selectedStart;
  };

  return (
    <div className="relative w-full pa11y-ignore-contrast-timeline">
      <div className="mb-2 flex items-center justify-between gap-3 text-xs text-gray-500">
        <span
          className="font-medium text-gray-700"
          data-testid="timeline-selected-range"
        >
          {selectedRangeLabel}
        </span>
        <span className="text-gray-500">Click a bar or drag across years</span>
      </div>

      <div
        className="sr-only"
        role="listbox"
        aria-label="Select year or year range"
      >
        {data.map((point) => (
          <button
            key={point.xKey}
            type="button"
            aria-pressed={isPointSelected(point)}
            onClick={() => selectPoint(point)}
          >
            {isBucketed
              ? `Select ${point.xKey} to ${point.xEnd}`
              : `Select ${point.xKey}`}
          </button>
        ))}
      </div>

      <div
        style={{ height: 110, width: '100%' }}
        className="select-none [&_*:focus-visible]:!outline-none [&_*:focus]:!outline-none [&_.recharts-surface]:!outline-none [&_.recharts-wrapper]:!outline-none"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            accessibilityLayer={false}
            margin={{ top: 5, right: 0, left: 0, bottom: 5 }}
            barCategoryGap={1}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp}
            onClick={onChartClick}
          >
            <XAxis
              dataKey="xKey"
              minTickGap={20}
              tick={{ fontSize: 10, fill: '#374151' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => (isBucketed ? `${v}s` : String(v))}
            />
            <Tooltip
              cursor={{ fill: 'rgba(37, 99, 235, 0.08)' }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const p = payload[0].payload as ChartPoint;
                  return (
                    <div className="z-50 rounded border border-gray-200 bg-white p-2 text-xs shadow-lg">
                      <p className="font-semibold">
                        {isBucketed ? `${p.xKey}-${p.xEnd}` : p.label}
                      </p>
                      <p className="text-gray-600">{`${payload[0].value} results`}</p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar
              dataKey="count"
              minPointSize={3}
              radius={[2, 2, 0, 0]}
              onMouseEnter={(point: ChartPoint) => setHoveredKey(point.xKey)}
              onMouseLeave={() => setHoveredKey(null)}
              className="cursor-pointer"
            >
              {data.map((point) => (
                <Cell
                  key={point.xKey}
                  fill={
                    isPointSelected(point)
                      ? '#1d4ed8'
                      : hoveredKey === point.xKey
                        ? '#2563eb'
                        : selectedRange
                          ? '#93c5fd'
                          : '#3b82f6'
                  }
                />
              ))}
            </Bar>
            {refAreaX1 != null && refAreaX2 != null && (
              <ReferenceArea
                x1={refAreaX1}
                x2={refAreaX2}
                stroke="none"
                fill="#3b82f6"
                fillOpacity={0.14}
              />
            )}
            {state.refAreaLeft && state.refAreaRight && (
              <ReferenceArea
                x1={state.refAreaLeft}
                x2={state.refAreaRight}
                stroke="none"
                fill="#3b82f6"
                fillOpacity={0.28}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <form noValidate onSubmit={handleManualSubmit} className="space-y-2 pb-3">
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] items-end gap-2">
          <label className="block min-w-0">
            <span className="mb-1 block text-xs font-medium text-gray-700">
              Start Year
            </span>
            <input
              type="text"
              aria-label="Start year"
              inputMode="numeric"
              pattern="[0-9]{4}"
              maxLength={4}
              value={manualStartYear}
              onChange={handleManualYearChange(setManualStartYear)}
              placeholder="1900"
              className="h-10 w-full rounded-md border border-gray-300 px-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </label>
          <label className="block min-w-0">
            <span className="mb-1 block text-xs font-medium text-gray-700">
              End Year
            </span>
            <input
              type="text"
              aria-label="End year"
              inputMode="numeric"
              pattern="[0-9]{4}"
              maxLength={4}
              value={manualEndYear}
              onChange={handleManualYearChange(setManualEndYear)}
              placeholder="2024"
              className="h-10 w-full rounded-md border border-gray-300 px-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </label>
          <button
            type="submit"
            className="h-10 rounded-md bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="h-10 rounded-md border border-gray-300 px-3 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
          >
            Clear
          </button>
        </div>
        {manualError && (
          <p className="text-xs text-red-600" role="alert">
            {manualError}
          </p>
        )}
      </form>
    </div>
  );
}
