import { render, screen, within, waitFor } from '@testing-library/react';
import { it, expect } from 'vitest';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { ReportContentLayout } from '../../components/analytics/ReportContentLayout';

it('uses visible headings rather than stale aliases or the sources class', async () => {
  const { rerender } = render(
    <ReportContentLayout report="Overview">
      <div className="analytics-content">
        <section className="analytics-section">
          <h2>Day by day</h2>
          <div className="analytics-panel" data-nav-label="Old label">
            <h3>Daily discovery</h3>
          </div>
        </section>
        <section className="analytics-report-sources">
          <h2>Actual source heading</h2>
        </section>
      </div>
    </ReportContentLayout>
  );
  const nav = await screen.findByRole('navigation', {
    name: 'Overview sections',
  });
  for (const link of within(nav).getAllByRole('link')) {
    const target = document.getElementById(
      link.getAttribute('href')!.slice(1)
    )!;
    expect(target.querySelector('h2,h3')?.textContent).toBe(link.textContent);
  }
  expect(within(nav).queryByText('Old label')).not.toBeInTheDocument();
  expect(within(nav).getByText('Day by day')).toBeInTheDocument();
  rerender(
    <ReportContentLayout report="Overview">
      <div className="analytics-content">
        <section className="analytics-panel">
          <h2>Updated heading</h2>
        </section>
        <section className="analytics-panel">
          <h2>Other heading</h2>
        </section>
      </div>
    </ReportContentLayout>
  );
  await waitFor(() =>
    expect(within(nav).getByText('Updated heading')).toBeInTheDocument()
  );
});

it('has no WCAG violations in the real section navigation layout', async () => {
  const { container } = render(
    <ReportContentLayout report="Overview">
      <main className="analytics-content">
        <section className="analytics-section">
          <h2>Daily activity</h2>
          <p>Daily report</p>
        </section>
        <section className="analytics-section">
          <h2>Sources</h2>
          <p>Data provenance</p>
        </section>
      </main>
    </ReportContentLayout>
  );
  await screen.findByRole('navigation', { name: 'Overview sections' });
  expect((await axeWithWCAG22(container)).violations).toEqual([]);
});
