import { render, screen } from '@testing-library/react';
import { axeWithWCAG22 } from '../../../test-utils/axe';
import { BrowserRouter } from 'react-router';
import { H3HexDataTable } from '../../../components/map/H3HexDataTable';

function renderTable(props: Parameters<typeof H3HexDataTable>[0]) {
  return render(
    <BrowserRouter>
      <H3HexDataTable {...props} />
    </BrowserRouter>
  );
}

describe('H3HexDataTable', () => {
  it('renders table with hex data', () => {
    renderTable({
      hexes: [
        { h3: '861f1ee47ffffff', count: 42 },
        { h3: '861f1ee4fffffff', count: 100 },
      ],
      resolution: 6,
    });

    expect(
      screen.getByRole('region', { name: /H3 hex grid data/i })
    ).toBeInTheDocument();
    expect(screen.getByText('861f1ee47ffffff')).toBeInTheDocument();
    expect(screen.getByText('861f1ee4fffffff')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
    const links = screen.getAllByRole('link', { name: /Search this hex/i });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute(
      'href',
      expect.stringContaining('861f1ee47ffffff')
    );
  });

  it('shows empty state when no hexes', () => {
    renderTable({ hexes: [], resolution: 6 });
    expect(screen.getByText(/No hex data in view/i)).toBeInTheDocument();
  });

  it('shows loading state', () => {
    renderTable({ hexes: [], resolution: 6, loading: true });
    expect(screen.getByText(/Loading hex data/i)).toBeInTheDocument();
  });

  it('has no accessibility violations with data', async () => {
    const { container } = renderTable({
      hexes: [
        { h3: '861f1ee47ffffff', count: 42 },
        { h3: '861f1ee4fffffff', count: 100 },
      ],
      resolution: 6,
    });
    const results = await axeWithWCAG22(container);
    expect(results).toHaveNoViolations();
  });

  it('has no accessibility violations when empty', async () => {
    const { container } = renderTable({ hexes: [], resolution: 6 });
    const results = await axeWithWCAG22(container);
    expect(results).toHaveNoViolations();
  });
});
