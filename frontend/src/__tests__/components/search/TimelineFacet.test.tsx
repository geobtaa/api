import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { TimelineFacet } from '../../../components/search/TimelineFacet';

// Mock Recharts since it renders on canvas/SVG and is hard to test interactively in JSDOM
vi.mock('recharts', () => {
  const OriginalModule = vi.importActual('recharts');
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
    BarChart: ({ children }: any) => (
      <div data-testid="bar-chart">{children}</div>
    ),
    Bar: () => <div data-testid="bar" />,
    Cell: () => null,
    Tooltip: () => <div data-testid="tooltip" />,
    ReferenceArea: () => <div data-testid="reference-area" />,
    XAxis: () => null,
  };
});

describe('TimelineFacet', () => {
  const mockFacet = {
    id: 'year_histogram',
    type: 'terms',
    attributes: {
      hits: 100,
      label: 'Year',
      items: [
        [1900, 10],
        [1950, 20],
        [2000, 30],
      ] as any,
    },
    links: { self: '...' },
  };

  it('renders the selected range label and always-visible year fields', () => {
    render(
      <TimelineFacet
        facet={mockFacet}
        selectedRange={null}
        onChange={() => {}}
      />
    );
    expect(screen.getByText('All Years')).toBeInTheDocument();
    expect(screen.getByLabelText('Start year')).toHaveValue('1900');
    expect(screen.getByLabelText('End year')).toHaveValue('2000');
  });

  it('renders the BarChart', () => {
    render(
      <TimelineFacet
        facet={mockFacet}
        selectedRange={null}
        onChange={() => {}}
      />
    );
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('renders selected range text', () => {
    render(
      <TimelineFacet
        facet={mockFacet}
        selectedRange={{ start: 1950, end: 2000 }}
        onChange={() => {}}
      />
    );
    expect(screen.getByText('1950 - 2000')).toBeInTheDocument();
  });

  it('renders open-ended selected range text', () => {
    render(
      <TimelineFacet
        facet={mockFacet}
        selectedRange={{ start: 1950, end: null }}
        onChange={() => {}}
      />
    );

    expect(screen.getByText('1950+')).toBeInTheDocument();
  });

  it('prefills manual entry fields with available min and max years when no range is active', () => {
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={() => {}}
      />
    );

    expect(screen.getByLabelText('Start year')).toHaveValue('1900');
    expect(screen.getByLabelText('End year')).toHaveValue('2000');
  });

  it('prefills manual entry fields from the selected range', () => {
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={{ start: 1950, end: 2000 }}
        onChange={() => {}}
      />
    );

    expect(screen.getByLabelText('Start year')).toHaveValue('1950');
    expect(screen.getByLabelText('End year')).toHaveValue('2000');
  });

  it('preserves a partial active range in manual entry', () => {
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={{ start: 1950, end: null }}
        onChange={() => {}}
      />
    );

    expect(screen.getByLabelText('Start year')).toHaveValue('1950');
    expect(screen.getByLabelText('End year')).toHaveValue('');
  });

  it('requires at least one year before applying', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Start year'));
    await user.clear(screen.getByLabelText('End year'));
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(
      screen.getByText('Enter a start year, an end year, or both.')
    ).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('validates manual entry as 4-digit years', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Start year'));
    await user.type(screen.getByLabelText('Start year'), '950');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(
      screen.getByText('Enter years as 4-digit numbers.')
    ).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('allows start-only manual year input', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Start year'));
    await user.clear(screen.getByLabelText('End year'));
    await user.type(screen.getByLabelText('Start year'), '1950');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onChange).toHaveBeenCalledWith({ start: 1950, end: null });
  });

  it('allows end-only manual year input', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Start year'));
    await user.clear(screen.getByLabelText('End year'));
    await user.type(screen.getByLabelText('End year'), '1950');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onChange).toHaveBeenCalledWith({ start: null, end: 1950 });
  });

  it('normalizes reversed manual year input before applying', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.clear(screen.getByLabelText('Start year'));
    await user.clear(screen.getByLabelText('End year'));
    await user.type(screen.getByLabelText('Start year'), '2000');
    await user.type(screen.getByLabelText('End year'), '1950');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(onChange).toHaveBeenCalledWith({ start: 1950, end: 2000 });
  });

  it('clears the active year range from manual mode', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={{ start: 1950, end: 2000 }}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Clear' }));

    expect(onChange).toHaveBeenCalledWith(null);
  });

  it('selects a single year from a focused chart bar control', async () => {
    const onChange = vi.fn();
    render(
      <TimelineFacet
        facet={mockFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Select 1950' }));

    expect(onChange).toHaveBeenCalledWith({ start: 1950, end: 1950 });
  });

  it('selects a decade bucket from a focused chart bar control', async () => {
    const manyYearFacet = {
      ...mockFacet,
      attributes: {
        ...mockFacet.attributes,
        items: Array.from({ length: 60 }, (_, index) => [1900 + index, 1]),
      },
    };
    const onChange = vi.fn();

    render(
      <TimelineFacet
        facet={manyYearFacet as any}
        selectedRange={null}
        onChange={onChange}
      />
    );

    const user = userEvent.setup();
    await user.click(
      screen.getByRole('button', { name: 'Select 1930 to 1939' })
    );

    expect(onChange).toHaveBeenCalledWith({ start: 1930, end: 1939 });
  });
});
