import React from 'react';
import { vi } from 'vitest';
import {
  render,
  screen,
  fireEvent,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import {
  CitationTable,
  type CitationStyle,
} from '../../../components/resource/CitationTable';

const renderWithRouter = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>);

describe('CitationTable', () => {
  const defaultProps = {
    citation: 'Author. (2023). Test Title. Publisher. https://example.com',
    permalink: 'https://geoportal.example.org/resources/123',
  };

  it('renders without crashing', () => {
    renderWithRouter(<CitationTable {...defaultProps} />);
    expect(screen.getByText('Cite & Reference')).toBeInTheDocument();
  });

  it('displays the citation text', () => {
    renderWithRouter(<CitationTable {...defaultProps} />);
    expect(screen.getByText(defaultProps.citation)).toBeInTheDocument();
  });

  it('displays the permalink input', () => {
    renderWithRouter(<CitationTable {...defaultProps} />);
    const input = screen.getByDisplayValue(defaultProps.permalink);
    expect(input).toBeInTheDocument();
  });

  it('renders Export section when resourceId is provided', () => {
    renderWithRouter(
      <CitationTable {...defaultProps} resourceId="test-resource-456" />
    );
    expect(
      screen.getByText('Export for citation tools')
    ).toBeInTheDocument();
    expect(screen.getByText('RIS')).toBeInTheDocument();
    expect(screen.getByText('BibTeX')).toBeInTheDocument();
    expect(screen.getByText('JSON-LD')).toBeInTheDocument();
  });

  it('Export RIS link has correct href', () => {
    renderWithRouter(
      <CitationTable {...defaultProps} resourceId="abc-123" />
    );
    const risLink = screen.getByRole('link', { name: /RIS/i });
    expect(risLink).toHaveAttribute(
      'href',
      expect.stringContaining('/resources/abc-123/citation/ris')
    );
    expect(risLink).toHaveAttribute('download', 'abc-123.ris');
  });

  it('Export BibTeX link has correct href', () => {
    renderWithRouter(
      <CitationTable {...defaultProps} resourceId="xyz-789" />
    );
    const bibLink = screen.getByRole('link', { name: /BibTeX/i });
    expect(bibLink).toHaveAttribute(
      'href',
      expect.stringContaining('/resources/xyz-789/citation/bibtex')
    );
    expect(bibLink).toHaveAttribute('download', 'xyz-789.bib');
  });

  it('renders style selector when citations prop has multiple styles', () => {
    const citations: Partial<Record<CitationStyle, string>> = {
      apa: 'APA format citation',
      mla: 'MLA format citation',
      chicago: 'Chicago format citation',
    };
    renderWithRouter(
      <CitationTable
        citation={citations.apa!}
        citations={citations}
        permalink={defaultProps.permalink}
      />
    );
    const selector = screen.getByRole('combobox');
    expect(selector).toBeInTheDocument();
    expect(selector).toHaveValue('apa');
  });

  it('does not render style selector when only citation (no citations)', () => {
    renderWithRouter(<CitationTable {...defaultProps} />);
    const selector = screen.queryByRole('combobox');
    expect(selector).not.toBeInTheDocument();
  });

  it('switches displayed citation when style selector changes', () => {
    const citations: Partial<Record<CitationStyle, string>> = {
      apa: 'APA 7th citation text',
      mla: 'MLA 9th citation text',
    };
    renderWithRouter(
      <CitationTable
        citation={citations.apa!}
        citations={citations}
        permalink={defaultProps.permalink}
      />
    );
    expect(screen.getByText('APA 7th citation text')).toBeInTheDocument();
    const selector = screen.getByRole('combobox');
    fireEvent.change(selector, { target: { value: 'mla' } });
    expect(screen.getByText('MLA 9th citation text')).toBeInTheDocument();
  });

  it('copies citation to clipboard when Copy button clicked', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      writable: true,
      configurable: true,
    });

    renderWithRouter(<CitationTable {...defaultProps} />);
    const copyButton = screen.getByTitle('Copy citation');
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(defaultProps.citation);
    });
  });

  it('copies permalink to clipboard when permalink Copy clicked', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      writable: true,
      configurable: true,
    });

    renderWithRouter(<CitationTable {...defaultProps} />);
    const copyButton = screen.getByTitle('Copy permalink');
    fireEvent.click(copyButton);

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledWith(defaultProps.permalink);
    });
  });

  it('renders when citation is empty but citations provided', () => {
    const citations = {
      apa: 'APA citation',
      mla: 'MLA citation',
    };
    renderWithRouter(
      <CitationTable
        citation=""
        citations={citations}
        permalink={defaultProps.permalink}
      />
    );
    expect(screen.getByText('APA citation')).toBeInTheDocument();
  });
});
