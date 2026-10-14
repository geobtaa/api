import { renderAnalytics as render } from '../utils/renderAnalytics';
import { fireEvent, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, expect, it } from 'vitest';
import { ZeroResultReport } from '../../components/analytics/ZeroResultReport';
import { zeroQueryCategory } from '../../data/analytics/zeroQueryCategory';

function report(searches = 7545, zeroResults = 1455) {
  render(
    <MemoryRouter>
      <ZeroResultReport
        period="August 2026"
        searches={searches}
        zeroResults={zeroResults}
        withQuery={758}
        queries={[
          { term: 'redlining', count: 5 },
          { term: '123 Main Street', count: 10 },
        ]}
      />
    </MemoryRouter>
  );
}
describe('ZeroResultReport', () => {
  it.each([
    [7545, 1455, '19.3%'],
    [6457, 1098, '17.0%'],
    [14002, 2553, '18.2%'],
  ])(
    'uses the full period denominator (%s searches)',
    (searches, zeros, rate) => {
      report(searches, zeros);
      expect(screen.getByText(rate)).toBeInTheDocument();
      expect(
        screen
          .getByRole('img', { name: /Search outcomes:/ })
          .getAttribute('aria-label')
      ).toContain(rate);
    }
  );
  it('keeps chart coverage explicit and retains full-period percentages when filtering', () => {
    report();
    const chart = screen.getByRole('img', {
      name: /Topics in searches without results:/,
    });
    expect(chart).toHaveAccessibleName(
      /Address and street search 10 \(66.7%\)/
    );
    const original = chart.getAttribute('aria-label');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Zero-result category' }),
      { target: { value: 'Subject-only search' } }
    );
    const ranking = screen.getByRole('region', {
      name: 'Search terms without results',
    });
    expect(within(ranking).getAllByRole('article')).toHaveLength(1);
    expect(
      within(ranking).getByText('0.3% of all zero-result searches')
    ).toBeInTheDocument();
    expect(chart.getAttribute('aria-label')).toBe(original);
    expect(
      screen.getByText(/not all 1,455 zero-result searches/)
    ).toBeInTheDocument();
  });
  it('filters ranked queries and resets the toolbar', () => {
    report();
    fireEvent.change(screen.getByRole('searchbox', { name: 'Find a query' }), {
      target: { value: 'missing-query' },
    });
    expect(screen.getByText(/No queries match/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(
      within(
        screen.getByRole('region', { name: 'Search terms without results' })
      ).getAllByRole('article')
    ).toHaveLength(2);
  });
  it('shows English readings, filters by translation, and preserves original links', () => {
    render(
      <MemoryRouter>
        <ZeroResultReport
          period="September 2026"
          searches={5536}
          zeroResults={754}
          withQuery={545}
          queries={[
            { term: 'قم ایران', count: 10 },
            { term: 'redlining', count: 3 },
          ]}
        />
      </MemoryRouter>
    );
    expect(screen.getByText(/Qom, Iran/)).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox', { name: 'Find a query' }), {
      target: { value: 'Qom' },
    });
    const ranking = screen.getByRole('region', {
      name: 'Search terms without results',
    });
    expect(within(ranking).getAllByRole('article')).toHaveLength(1);
    expect(
      within(ranking).getByRole('link', { name: 'قم ایران' })
    ).toHaveAttribute('href', `/search?q=${encodeURIComponent('قم ایران')}`);
  });
  it('preserves reviewed categories and leaves unknown queries unclassified', () => {
    expect(zeroQueryCategory('redlining')).toBe('Subject-only search');
    expect(zeroQueryCategory('41.123,-87.234')).toBe(
      'Coordinates and Plus Codes'
    );
    expect(zeroQueryCategory('unrecognized opaque wording')).toBe(
      'Unclassified or ambiguous'
    );
  });
});
