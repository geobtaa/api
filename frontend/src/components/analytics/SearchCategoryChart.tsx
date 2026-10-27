import { chartTheme } from './chartTheme';
import { ChartPie } from 'lucide-react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { ReportPanelHeader } from './ReportPanelHeader';

const colors = [
  '#003c5b',
  '#2563eb',
  '#047857',
  '#7c3aed',
  '#b45309',
  '#be185d',
  '#0891b2',
  '#64748b',
];
const number = new Intl.NumberFormat('en-US');
type SearchCategory = { category: string; searches: number; queries: number };

export function SearchCategoryChart({
  categories,
}: {
  categories: SearchCategory[];
}) {
  return (
    <section className="analytics-panel analytics-comparison-panel analytics-search-categories">
      <ReportPanelHeader title="Search categories" icon={ChartPie} />
      <SearchCategoryDistribution categories={categories} />
    </section>
  );
}

export function SearchCategoryDistribution({
  categories,
  description = 'Search counts by suggested category, covering the top 50 queries only.',
  label = 'Search category distribution',
}: {
  categories: SearchCategory[];
  description?: string;
  label?: string;
}) {
  const rows = [...categories].sort((a, b) => b.searches - a.searches);
  const total = rows.reduce((sum, row) => sum + row.searches, 0);
  return (
    <>
      <p className="analytics-comparison-note">{description}</p>
      {total > 0 ? (
        <div
          role="img"
          aria-label={`${label}: ${rows.map((row) => `${row.category}: ${number.format(row.searches)}`).join('; ')}`}
        >
          <ResponsiveContainer
            width="100%"
            height={200}
            minWidth={0}
            initialDimension={{ width: 400, height: 200 }}
          >
            <PieChart accessibilityLayer>
              <Pie
                data={rows}
                dataKey="searches"
                nameKey="category"
                outerRadius="85%"
                stroke="#fff"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {rows.map((row, index) => (
                  <Cell
                    key={row.category}
                    fill={colors[index % colors.length]}
                  />
                ))}
              </Pie>
              <Tooltip
                contentStyle={chartTheme.tooltip}
                labelStyle={chartTheme.tooltipLabel}
                formatter={(value, category) => [
                  `${number.format(Number(value))} searches`,
                  String(category),
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p>No categorized searches are available for this period.</p>
      )}
      <ul
        className="analytics-search-category-legend"
        aria-label="Search category counts"
      >
        {rows.map((row, index) => (
          <li key={row.category}>
            <span
              className="analytics-search-category-dot"
              style={{ background: colors[index % colors.length] }}
              aria-hidden="true"
            />
            <div>
              <span className="analytics-search-category-name">
                {row.category}
              </span>
              <span className="analytics-search-category-value">
                <strong>{number.format(row.searches)}</strong>
                <span aria-hidden="true"> · </span>
                {total ? `${Math.round((row.searches / total) * 100)}%` : '—'}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
