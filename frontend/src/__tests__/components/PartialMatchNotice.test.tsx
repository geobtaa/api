import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PartialMatchNotice } from '../../components/search/PartialMatchNotice';

describe('PartialMatchNotice', () => {
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
