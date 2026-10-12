import { renderAnalytics as render } from '../utils/renderAnalytics';
import { screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { PopularContentReport } from '../../components/analytics/PopularContentReport';
import { AllTimeAnalyticsPage } from '../../components/analytics/AllTimeAnalyticsPage';
import snapshots from '../../data/analytics/monthlySnapshots.json';

it('uses monthly views for momentum, matching ranks, and scoped classification bars', () => {
  const rows = snapshots['2026-09'].topResources.slice(0, 2).map((row, i) => ({
    ...row,
    views: i ? 10 : 20,
    previousMonthViews: i ? null : 10,
    resourceClass: 'Maps',
    resourceType: 'Topographic maps',
  }));
  const { container } = render(
    <MemoryRouter>
      <PopularContentReport
        title="Top content"
        reportMonth="September"
        topResources={rows}
        topCollections={[
          { id: 'collection', title: 'Test collection', views: 42 },
        ]}
        collectionNote="Collections"
        topDownloadedResources={[]}
        downloadClicks={0}
        downloadNote="Downloads"
      />
    </MemoryRouter>
  );
  expect(screen.getByText('+100.0%')).toBeInTheDocument();
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0);
  expect(screen.queryByText('2H pulse')).not.toBeInTheDocument();
  for (const rank of screen.getAllByLabelText('Rank 1')) {
    expect(rank).toHaveTextContent('#1');
    expect(rank).toHaveClass('analytics-rank-number--leader');
  }
  const collections = screen
    .getByRole('heading', { name: 'Top collections' })
    .closest('aside')!;
  expect(collections).toHaveTextContent('42views');
  expect(collections).not.toHaveTextContent('filtered searches');
  const bars = container.querySelectorAll(
    '.analytics-ranking-copy .analytics-collection-track i'
  );
  expect(bars[0]).toHaveStyle({ width: '100%' });
  expect(bars[1]).toHaveStyle({ width: '50%' });
  const classes = screen
    .getByRole('heading', { name: 'Top resource classes' })
    .closest('article')!;
  expect(within(classes).getByText('30')).toBeInTheDocument();
  expect(classes).toHaveTextContent('Within the 2 resources ranked above');
});

it('preserves recorded classifications in the All Time report', () => {
  render(
    <MemoryRouter initialEntries={['/analytics/content?month=all']}>
      <AllTimeAnalyticsPage reportId="content" />
    </MemoryRouter>
  );
  const classes = screen
    .getByRole('heading', { name: 'Top resource classes' })
    .closest('article')!;
  const types = screen
    .getByRole('heading', { name: 'Top resource types' })
    .closest('article')!;
  expect(within(classes).getByText('Maps')).toBeInTheDocument();
  expect(within(types).getByText('Fire insurance maps')).toBeInTheDocument();
  expect(screen.queryByText('Momentum')).not.toBeInTheDocument();
  expect(screen.queryByText('Monthly only')).not.toBeInTheDocument();
  expect(screen.queryByText('vs prior month')).not.toBeInTheDocument();
});

it('shows momentum on every monthly ranking', () => {
  const data = snapshots['2026-09'];
  const { container } = render(
    <MemoryRouter>
      <PopularContentReport
        title="Popular content"
        reportMonth="September"
        reportPeriod="2026-09"
        topResources={data.topResources}
        topCollections={[{ id: 'test', title: 'Collection', views: 42 }]}
        collectionNote="Collections"
        topDownloadedResources={data.topDownloads}
        downloadClicks={data.summary.downloadClicks}
        downloadNote="Downloads"
      />
    </MemoryRouter>
  );
  for (const panel of container.querySelectorAll('.analytics-panel')) {
    const firstRow = panel.querySelector('.analytics-ranking-item');
    expect(
      firstRow?.querySelector('.analytics-ranking-trend')
    ).toHaveTextContent('vs prior month');
  }
});
