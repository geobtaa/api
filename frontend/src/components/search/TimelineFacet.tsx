import React, { useMemo } from "react";
import { Facet } from "../../types/facet";
import {
    BarChart,
    Bar,
    Tooltip,
    ResponsiveContainer,
    ReferenceArea,
    XAxis,
} from "recharts";

interface TimelineFacetProps {
    facet: Facet;
    selectedRange: [number, number] | null;
    onChange: (range: [number, number] | null) => void;
}

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

    // 1. Process data
    const data = useMemo(() => {
        if (!facet.attributes.items || facet.attributes.items.length === 0)
            return [];

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

        // Sort by year
        return items.sort((a, b) => a.year - b.year);
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
            setState({ ...state, isDragging: false, refAreaLeft: undefined, refAreaRight: undefined });

            // Just a click or invalid drag
            if (!state.refAreaLeft || !state.refAreaRight || state.refAreaLeft === state.refAreaRight) {
                // If it was just a click (or tiny drag that resolved to same year),
                // we could treat it as "reset" or "single year select".
                // Current requirement implies "zoom/pan" replacement implies range.
                // Let's treat "click" on same spot as clearing the filter if one exists,
                // or setting a single year if we want that.
                // For now, let's say if start == end, we clear the filter (reset).
                onChange(null);
                return;
            }

            let start = Number(state.refAreaLeft);
            let end = Number(state.refAreaRight);

            if (start > end) [start, end] = [end, start];

            onChange([start, end]);
        }
    };

    const startYear = selectedRange ? selectedRange[0] : null;
    const endYear = selectedRange ? selectedRange[1] : null;

    return (
        <div className="w-full">
            <div className="flex justify-between items-center px-1 mb-1 text-xs text-gray-500 h-5">
                <span className="italic text-gray-400">
                    Drag to filter
                </span>
                <span className="font-medium text-gray-700">
                    {startYear && endYear
                        ? `${startYear} - ${endYear}`
                        : "All Years"}
                </span>
            </div>

            <div style={{ height: 100, width: "100%" }} className="select-none">
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
                            dataKey="year"
                            minTickGap={20}
                            tick={{ fontSize: 10, fill: "#6b7280" }}
                            axisLine={false}
                            tickLine={false}
                        />
                        <Tooltip
                            cursor={{ fill: "transparent" }}
                            content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                    return (
                                        <div className="bg-white border border-gray-200 p-2 shadow-lg rounded text-xs z-50">
                                            <p className="font-semibold">{`Year: ${payload[0].payload.year}`}</p>
                                            <p className="text-gray-600">{`Count: ${payload[0].value}`}</p>
                                        </div>
                                    );
                                }
                                return null;
                            }}
                        />
                        <Bar dataKey="count" fill="#3b82f6" />
                        {selectedRange && (
                            <ReferenceArea x1={selectedRange[0]} x2={selectedRange[1]} strokeOpacity={0.3} fill="#3b82f6" fillOpacity={0.1} />
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
