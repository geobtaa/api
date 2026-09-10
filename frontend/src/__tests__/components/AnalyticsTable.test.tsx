import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AnalyticsTable } from '../../components/analytics/AnalyticsTable';

function Example() {
  return (
    <AnalyticsTable>
      <caption>Provider totals</caption>
      <thead>
        <tr>
          <th scope="col">Provider</th>
          <th scope="col">Views</th>
          <th scope="col">Change</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">
            <a href="/ohio">Ohio State</a>
          </th>
          <td>1,200</td>
          <td>
            {'+'}
            {'1,000'}%
          </td>
        </tr>
        <tr>
          <th scope="row">Indiana</th>
          <td>20</td>
          <td>−3%</td>
        </tr>
        <tr>
          <th scope="row">Missing provider</th>
          <td>Unavailable</td>
          <td>N/A</td>
        </tr>
        <tr>
          <th scope="row">Michigan</th>
          <td>100</td>
          <td>0%</td>
        </tr>
      </tbody>
    </AnalyticsTable>
  );
}
const names = () =>
  screen.getAllByRole('rowheader').map((cell) => cell.textContent);

describe('AnalyticsTable', () => {
  it('sorts formatted numbers both ways and keeps missing values last', () => {
    render(<Example />);
    fireEvent.click(screen.getByRole('button', { name: 'Views' }));
    expect(names()).toEqual([
      'Indiana',
      'Michigan',
      'Ohio State',
      'Missing provider',
    ]);
    expect(screen.getByRole('columnheader', { name: 'Views' })).toHaveAttribute(
      'aria-sort',
      'ascending'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Views' }));
    expect(names()).toEqual([
      'Ohio State',
      'Michigan',
      'Indiana',
      'Missing provider',
    ]);
    expect(screen.getByRole('columnheader', { name: 'Views' })).toHaveAttribute(
      'aria-sort',
      'descending'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Change' }));
    expect(names()).toEqual([
      'Indiana',
      'Michigan',
      'Ohio State',
      'Missing provider',
    ]);
    expect(screen.getByRole('link', { name: 'Ohio State' })).toHaveAttribute(
      'href',
      '/ohio'
    );
  });

  it('filters all cells, reports empty results, and resets to original order', () => {
    render(<Example />);
    const filter = screen.getByRole('searchbox', {
      name: 'Filter Provider totals',
    });
    fireEvent.change(filter, { target: { value: 'STATE 1,200' } });
    expect(names()).toEqual(['Ohio State']);
    expect(screen.getByRole('status')).toHaveTextContent('1 of 4 rows');
    fireEvent.change(filter, { target: { value: 'no such provider' } });
    expect(screen.getByText(/No matching rows/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    fireEvent.click(screen.getByRole('button', { name: 'Provider' }));
    expect(names()[0]).toBe('Indiana');
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(names()).toEqual([
      'Ohio State',
      'Indiana',
      'Missing provider',
      'Michigan',
    ]);
    expect(
      within(screen.getByRole('table')).getByText('Provider totals')
    ).toBeInTheDocument();
  });
});

it('filters collapsed custom content and sorts by its explicit value', () => {
  render(
    <AnalyticsTable>
      <caption>Context test</caption>
      <thead>
        <tr>
          <th scope="col">Query</th>
          <th scope="col">Context</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">redlining</th>
          <td data-filter-value="Exclude Datasets" data-sort-value={3}>
            <details>
              <summary>Expand</summary>
            </details>
          </td>
        </tr>
        <tr>
          <th scope="row">other</th>
          <td data-filter-value="Include Maps" data-sort-value={1}>
            One combination
          </td>
        </tr>
      </tbody>
    </AnalyticsTable>
  );
  fireEvent.change(screen.getByRole('searchbox'), {
    target: { value: 'Exclude Datasets' },
  });
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(2);
  expect(
    screen.getByRole('rowheader', { name: 'redlining' })
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
  fireEvent.click(screen.getByRole('button', { name: 'Context' }));
  expect(
    within(screen.getByRole('table')).getAllByRole('row')[1]
  ).toHaveTextContent('other');
});
