import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MatchGroupHeading } from '../../components/search/MatchGroupHeading';

const matching = {
  mode: 'all_terms_then_partial',
  broadened: true,
  version: 'v2',
  all_terms_count: 1,
  partial_terms_count: 14,
} as const;

describe('MatchGroupHeading', () => {
  it('labels the boundary after the first strict result', () => {
    const { rerender } = render(
      <MatchGroupHeading matching={matching} absoluteIndex={0} firstOnPage />
    );
    expect(screen.getByRole('heading')).toHaveTextContent(
      'Matches all search terms'
    );
    rerender(
      <MatchGroupHeading
        matching={matching}
        absoluteIndex={1}
        firstOnPage={false}
      />
    );
    expect(screen.getByRole('heading')).toHaveTextContent('Partial matches');
    rerender(
      <MatchGroupHeading
        matching={matching}
        absoluteIndex={2}
        firstOnPage={false}
      />
    );
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });
  it('labels continuation pages without repeating the strict heading', () => {
    render(
      <MatchGroupHeading matching={matching} absoluteIndex={10} firstOnPage />
    );
    expect(screen.getByRole('heading')).toHaveTextContent('Partial matches');
  });
  it('does not add a boundary to ordinary or legacy results', () => {
    render(<MatchGroupHeading absoluteIndex={0} firstOnPage />);
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });
});
