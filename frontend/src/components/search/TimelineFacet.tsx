import React, { useMemo } from 'react';
import { Facet } from '../../types/facet';
import {
  BarChart,
  Bar,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
  XAxis,
} from 'recharts';

/** When there are more than this many years, show decade buckets so bars stay visible. */
const BUCKET_THRESHOLD = 50;
const DECADE_SIZE = 10;

interface TimelineFacetProps {
  facet: Facet;
  selectedRange: [number, number] | null;
  onChange: (range: [number, number] | null) => void;
}

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

  // Process data: raw years, or decade buckets when there are too many years
  const { data, isBucketed } = useMemo(() => {
    if (!facet.attributes.items || facet.attributes.items.length === 0)
      return { data: [], isBucketed: false };

    const minValidYear = 1000;
    const maxValidYear = 2030;

    const items = facet.attributes.items
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
      .filter((d) => d.year >= minValidYear && d.year <= maxValidYear);

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

  if (data.length === 0) return null;

  const onMouseDown = (e: any) => {
    if (e && e.activeLabel) {
      setState({ ...state, refAreaLeft: e.activeLabel, isDragging: true });
    }
  };

  const onMouseMove = (e: any) => {
    if (state.isDragging && e && e.activeLabel) {
      setState({ ...state, refAreaRight: e.activeLabel });
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
        onChange(null);
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
        onChange([leftKey, rightEnd]);
      } else {
        onChange([leftKey, rightKey]);
      }
    }
  };

  const startYear = selectedRange ? selectedRange[0] : null;
  const endYear = selectedRange ? selectedRange[1] : null;

  const refAreaX1 = selectedRange
    ? isBucketed
      ? Math.floor(selectedRange[0] / DECADE_SIZE) * DECADE_SIZE
      : selectedRange[0]
    : null;
  const refAreaX2 = selectedRange
    ? isBucketed
      ? Math.floor(selectedRange[1] / DECADE_SIZE) * DECADE_SIZE
      : selectedRange[1]
    : null;

  return (
    <div className="w-full">
      <div className="flex justify-between items-center px-1 mb-1 text-xs text-gray-500 h-5">
        <span className="italic text-gray-400">Drag to filter</span>
        <span className="font-medium text-gray-700">
          {startYear && endYear ? `${startYear} - ${endYear}` : 'All Years'}
        </span>
      </div>

      <div style={{ height: 100, width: '100%' }} className="select-none">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 5, right: 0, left: 0, bottom: 5 }}
            barCategoryGap={1}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp} // Stop dragging if leaving chart
          >
            <XAxis
              dataKey="xKey"
              minTickGap={20}
              tick={{ fontSize: 10, fill: '#6b7280' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => (isBucketed ? `${v}s` : String(v))}
            />
            <Tooltip
              cursor={{ fill: 'transparent' }}
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const p = payload[0].payload as ChartPoint;
                  return (
                    <div className="bg-white border border-gray-200 p-2 shadow-lg rounded text-xs z-50">
                      <p className="font-semibold">
                        {isBucketed ? `${p.xKey}–${p.xEnd}` : p.label}
                      </p>
                      <p className="text-gray-600">{`Count: ${payload[0].value}`}</p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar
              dataKey="count"
              fill="#3b82f6"
              minPointSize={3}
              radius={[2, 2, 0, 0]}
            />
            {refAreaX1 != null && refAreaX2 != null && (
              <ReferenceArea
                x1={refAreaX1}
                x2={refAreaX2}
                strokeOpacity={0.3}
                fill="#3b82f6"
                fillOpacity={0.1}
              />
            )}
            {state.refAreaLeft && state.refAreaRight && (
              <ReferenceArea
                x1={state.refAreaLeft}
                x2={state.refAreaRight}
                strokeOpacity={0.3}
                fill="#3b82f6"
                fillOpacity={0.3}
              />
            )}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
