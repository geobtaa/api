import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router';
import {
  RuntimeAnalyticsPage,
  RuntimeReportView,
  type RuntimeReport,
} from '../../components/analytics/RuntimeAnalyticsPage';

const report: RuntimeReport = {
  comparison: [],
  collections: [],
  discoveryViews: [],
  memberResources: [],
  memberDaily: [],
  zeroCategories: [],
  schemaVersion: 1,
  revision: 'a'.repeat(64),
  period: '2027-02',
  start: '2027-02-01',
  endExclusive: '2027-03-01',
  complete: true,
  coverage: [],
  sourceCoverage: {},
  missingMonths: [],
  sources: { discovery: 'Recorded searches', members: 'Provider or code' },
  totals: {},
  daily: [],
  queries: [
    {
      query: 'water',
      category: 'Environment',
      count: 5,
      zeroResults: 3,
      context: [
        { constraints: { page: ['2'] }, count: 3, resultTotals: { '10': 3 } },
      ],
    },
  ],
  zeroQueries: [
    {
      query: 'water',
      category: 'Environment',
      count: 3,
      context: [
        { constraints: { page: ['2'] }, count: 3, resultTotals: { '10': 3 } },
      ],
    },
  ],
  resources: [],
  outlinks: [],
  downloads: [],
  downloadBreakdown: [],
  members: [
    { grouping: 'provider', name: 'County', inventory: 8, views: 4 },
    { grouping: 'code', name: 'University', inventory: 8, views: 4 },
  ],
  clients: [],
  endpoints: [],
  facets: [],
  categories: [{ category: 'Environment', count: 5 }],
  zeroResultPercent: 60,
  trackedVisits: { value: 4, status: 'estimated', definition: 'Not people' },
  latency: { meanMs: null, p95Ms: null },
};

describe('runtime analytics', () => {
  it('preserves query context, zero-result percentage and versioned downloads', () => {
    render(<RuntimeReportView report={report} active="discovery" />);
    expect(screen.getByText(/60.0%/)).toBeInTheDocument();
    expect(screen.getByText('1 recorded combinations')).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: 'Repeat search with recorded parameters',
      })
    ).toHaveAttribute('href', '/search?q=water&page=2');
    expect(
      screen.getByText(/empty displayed page can have a positive total/)
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole('link', { name: 'Download CSV' })[0]
    ).toHaveAttribute(
      'href',
      expect.stringContaining(`/2027-02/${report.revision}/download/queries`)
    );
  });
  it('switches between provider and contribution groupings', () => {
    render(<RuntimeReportView report={report} active="members" />);
    expect(screen.getAllByText('County').length).toBeGreaterThan(0);
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Group content by' }),
      {
        target: { value: 'code' },
      }
    );
    expect(screen.getAllByText('University').length).toBeGreaterThan(0);
    expect(screen.queryByText('County')).not.toBeInTheDocument();
  });
  it('does not silently substitute a month for an unsupported period', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          schemaVersion: 1,
          latest: '2027-02',
          throughExclusive: '2027-03-01',
          periods: [
            { id: '2027-02', revision: report.revision, complete: true },
          ],
        }),
      })
    );
    try {
      render(
        <MemoryRouter initialEntries={['/analytics?month=2029-01&runtime=1']}>
          <RuntimeAnalyticsPage />
        </MemoryRouter>
      );
      expect(await screen.findByRole('alert')).toHaveTextContent(
        'This period is unavailable'
      );
      expect(fetch).toHaveBeenCalledTimes(1);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

it('shows access rankings independently and labels unavailable audience measures', () => {
  const accessReport = {
    ...report,
    outlinks: [{ id: 'outlinked', title: 'Outlinked item', sourceClicks: 20 }],
    downloads: [{ id: 'downloaded', title: 'Downloaded item', downloads: 8 }],
    unavailable: { uniqueVisitors: 'No persistent person identifier.' },
  };
  const { rerender } = render(
    <RuntimeReportView report={accessReport} active="content" />
  );
  expect(screen.getByText('Outlinked item')).toBeInTheDocument();
  expect(screen.getByText('Downloaded item')).toBeInTheDocument();
  expect(
    screen.getByRole('heading', { name: 'Most downloaded resources' })
  ).toBeInTheDocument();
  rerender(<RuntimeReportView report={accessReport} active="overview" />);
  expect(screen.getByText('Unique Visitors: unavailable.')).toBeInTheDocument();
  fireEvent.change(
    screen.getByRole('combobox', { name: 'Audience chart metric' }),
    {
      target: { value: 'searches' },
    }
  );
  expect(
    screen.getByRole('combobox', { name: 'Audience chart metric' })
  ).toHaveValue('searches');
});
