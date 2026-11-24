import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PartialMatchNotice } from '../../components/search/PartialMatchNotice';

describe('PartialMatchNotice', () => {
  it('leaves mixed results to the group headings without an alert', () => {
    render(
      <PartialMatchNotice
        matching={{
          mode: 'all_terms_then_partial',
          broadened: true,
          version: 'v2',
          all_terms_count: 1,
          partial_terms_count: 14,
        }}
        totalCount={15}
      />
    );
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByText(/No results matched/)).not.toBeInTheDocument();
  });
  it('explains broader results', () => {
    render(
      <PartialMatchNotice
        matching={{ mode: 'partial_terms', broadened: true, version: 'v2' }}
        totalCount={14}
      />
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'No results matched all search terms. Showing partial matches.'
    );
  });

  it.each(['all_terms', 'literal'] as const)(
    'hides for %s matching',
    (mode) => {
      render(
        <PartialMatchNotice
          matching={{ mode, broadened: false, version: 'v2' }}
          totalCount={14}
        />
      );
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    }
  );

  it('leaves empty and legacy responses to the existing interface', () => {
    const { rerender } = render(<PartialMatchNotice totalCount={14} />);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    rerender(
      <PartialMatchNotice
        matching={{ mode: 'partial_terms', broadened: true, version: 'v2' }}
        totalCount={0}
      />
    );
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
