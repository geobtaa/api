import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { linkifyText } from '../../utils/linkifyText';

function Wrapper({ children }: { children: React.ReactNode }) {
  return <div>{children}</div>;
}

describe('linkifyText', () => {
  describe('plain text without URLs', () => {
    it('returns the original string when no URLs are present', () => {
      const text = 'This is plain text with no links.';
      const { container } = render(<Wrapper>{linkifyText(text)}</Wrapper>);
      expect(container).toHaveTextContent(text);
      expect(container.querySelector('a')).toBeNull();
    });

    it('returns empty string for empty input', () => {
      const { container } = render(<Wrapper>{linkifyText('')}</Wrapper>);
      expect(container).toHaveTextContent('');
    });

    it('returns empty string for nullish-like input', () => {
      const { container } = render(
        <Wrapper>{linkifyText('' as string)}</Wrapper>
      );
      expect(container).toHaveTextContent('');
    });
  });

  describe('URL detection and linkification', () => {
    it('converts a single URL into a clickable link', () => {
      const text = 'See https://example.com for more.';
      render(<Wrapper>{linkifyText(text)}</Wrapper>);
      const link = screen.getByRole('link', { name: /https:\/\/example\.com/ });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', 'https://example.com');
    });

    it('converts http URLs into links', () => {
      const text = 'Visit http://example.org';
      render(<Wrapper>{linkifyText(text)}</Wrapper>);
      const link = screen.getByRole('link', { name: /http:\/\/example\.org/ });
      expect(link).toHaveAttribute('href', 'http://example.org');
    });

    it('opens links in new tab with security attributes', () => {
      const text = 'Go to https://example.com';
      render(<Wrapper>{linkifyText(text)}</Wrapper>);
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('preserves surrounding text before and after the URL', () => {
      const text = 'See https://example.com for details.';
      const { container } = render(<Wrapper>{linkifyText(text)}</Wrapper>);
      expect(container).toHaveTextContent(
        'See https://example.com for details.'
      );
    });
  });

  describe('trailing punctuation', () => {
    it('trims closing parenthesis from href so link works', () => {
      const text = '(https://example.com/page)';
      render(<Wrapper>{linkifyText(text)}</Wrapper>);
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', 'https://example.com/page');
    });

    it('renders closing parenthesis as plain text after the link', () => {
      const text = '(https://example.com/page)';
      const { container } = render(<Wrapper>{linkifyText(text)}</Wrapper>);
      expect(container).toHaveTextContent('(https://example.com/page)');
      const link = screen.getByRole('link');
      expect(link).toHaveTextContent('https://example.com/page');
    });

    it('trims trailing quotes and brackets from href', () => {
      const text = 'Check "https://example.com" for info.';
      render(<Wrapper>{linkifyText(text)}</Wrapper>);
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', 'https://example.com');
    });
  });

  describe('multiple URLs', () => {
    it('linkifies multiple URLs in the same text', () => {
      const text = 'Visit https://a.com and https://b.com for more.';
      render(<Wrapper>{linkifyText(text)}</Wrapper>);
      const links = screen.getAllByRole('link');
      expect(links).toHaveLength(2);
      expect(links[0]).toHaveAttribute('href', 'https://a.com');
      expect(links[1]).toHaveAttribute('href', 'https://b.com');
    });
  });
});
