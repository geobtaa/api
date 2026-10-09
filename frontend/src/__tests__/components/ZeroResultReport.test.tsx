import { fireEvent, render, screen, within } from '@testing-library/react';
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
      name: /Zero-result query categories:/,
    });
    expect(chart).toHaveAccessibleName(
      /Address and street search 10 \(66.7%\)/
    );
    const original = chart.getAttribute('aria-label');
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Zero-result category' }),
      { target: { value: 'Subject-only search' } }
    );
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(within(table).getByText('0.3%')).toBeInTheDocument();
    expect(chart.getAttribute('aria-label')).toBe(original);
    expect(
      screen.getByText(/not all 1,455 zero-result searches/)
    ).toBeInTheDocument();
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
