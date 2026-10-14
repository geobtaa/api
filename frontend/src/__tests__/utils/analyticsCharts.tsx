/* eslint-disable react-refresh/only-export-components */
import type { ReactNode } from 'react';
const Chart = ({ children }: { children?: ReactNode }) => <svg>{children}</svg>;
const Mark = () => null;
/** Shared structural mocks; individual tests can override charts they inspect. */
export const analyticsCharts = {
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  ),
  AreaChart: Chart,
  BarChart: Chart,
  LineChart: Chart,
  PieChart: Chart,
  Area: Mark,
  Bar: Mark,
  Line: Mark,
  Pie: Mark,
  Cell: Mark,
  Legend: Mark,
  CartesianGrid: Mark,
  Tooltip: Mark,
  XAxis: Mark,
  YAxis: Mark,
};
