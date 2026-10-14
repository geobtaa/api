import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, it, expect } from 'vitest';
import { MemberPerformanceReport } from '../../components/analytics/MemberPerformanceReport';
import { memberPerformance } from '../../data/analytics/july2026';

describe('MemberPerformanceReport', () => {
  it('filters institutions and ranks by the selected metric while retaining content links', () => {
    render(
      <MemoryRouter>
        <MemberPerformanceReport members={memberPerformance} />
      </MemoryRouter>
    );
    expect(screen.getByText('18 of 18 institutions')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox'), {
      target: { value: 'USC' },
    });
    const usc = screen.getByRole('article');
    expect(within(usc).getByRole('heading')).toHaveTextContent(
      'University of Southern California'
    );
    expect(within(usc).getAllByLabelText('Unavailable')).toHaveLength(6);
    expect(
      within(usc).getByText('No data available for this reporting period.')
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Sort member performance'), {
      target: { value: 'downloadClicks' },
    });
    const leader = [...memberPerformance].sort(
      (a, b) => b.downloadClicks - a.downloadClicks
    )[0];
    expect(
      within(screen.getAllByRole('article')[0]).getByRole('heading')
    ).toHaveTextContent(leader.name);
    fireEvent.change(
      screen.getByRole('searchbox', { name: 'Filter institutions' }),
      { target: { value: 'University of Chicago' } }
    );
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByText('Top-viewed content:')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('searchbox'), {
      target: { value: 'not-an-institution' },
    });
    expect(
      screen.getByText('No institutions match your search.')
    ).toBeInTheDocument();
  });
});
