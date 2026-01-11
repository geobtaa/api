import { render, screen } from '@testing-library/react';
import { ResourceDescription } from '../../components/resource/ResourceDescription';

describe('ResourceDescription Component', () => {
  describe('Rendering', () => {
    it('renders description section with heading', () => {
      const description = ['This is a test description'];

      render(<ResourceDescription description={description} />);

      expect(
        screen.getByRole('heading', { name: 'Description' })
      ).toBeInTheDocument();
      expect(
        screen.getByText('This is a test description')
      ).toBeInTheDocument();
    });

    it('renders multiple description paragraphs', () => {
      const description = [
        'First description paragraph',
        'Second description paragraph',
        'Third description paragraph',
      ];

      render(<ResourceDescription description={description} />);

      expect(
        screen.getByRole('heading', { name: 'Description' })
      ).toBeInTheDocument();
      expect(
        screen.getByText('First description paragraph')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Second description paragraph')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Third description paragraph')
      ).toBeInTheDocument();
    });

    it('applies correct CSS classes to elements', () => {
      const description = ['Test description'];

      render(<ResourceDescription description={description} />);

      const section = screen
        .getByRole('heading', { name: 'Description' })
        .closest('section');
      expect(section).toHaveClass('mb-8');

      const heading = screen.getByRole('heading', { name: 'Description' });
      expect(heading).toHaveClass(
        'text-xl',
        'font-semibold',
        'text-gray-900',
        'mb-3'
      );

      const paragraph = screen.getByText('Test description');
      expect(paragraph).toHaveClass('text-gray-600', 'mb-2');
    });

    it('renders each description paragraph with unique key', () => {
      const description = ['First paragraph', 'Second paragraph'];

      render(<ResourceDescription description={description} />);

      const paragraphs = screen.getAllByText(/paragraph/);
      expect(paragraphs).toHaveLength(2);
      expect(paragraphs[0]).toHaveTextContent('First paragraph');
      expect(paragraphs[1]).toHaveTextContent('Second paragraph');
    });
  });

  describe('Edge Cases', () => {
    it('returns null when description is empty array', () => {
      const { container } = render(<ResourceDescription description={[]} />);

      expect(container.firstChild).toBeNull();
    });

    it('returns null when description is null', () => {
      const { container } = render(
        <ResourceDescription description={null as any} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('returns null when description is undefined', () => {
      const { container } = render(
        <ResourceDescription description={undefined as any} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('handles empty string in description array', () => {
      const description = [
        'Valid description',
        '',
        'Another valid description',
      ];

      render(<ResourceDescription description={description} />);

      expect(screen.getByText('Valid description')).toBeInTheDocument();
      expect(screen.getByText('Another valid description')).toBeInTheDocument();

      // Empty string should still render as an empty paragraph
      const paragraphs = screen.getAllByText(/description/);
      expect(paragraphs).toHaveLength(2); // Only non-empty descriptions
    });

    it('handles very long description text', () => {
      const longDescription = [
        'This is a very long description that might contain a lot of text and should still render properly without any issues or truncation.',
        "Another long paragraph with extensive content that tests the component's ability to handle substantial amounts of text in the description array.",
      ];

      render(<ResourceDescription description={longDescription} />);

      expect(screen.getByText(longDescription[0])).toBeInTheDocument();
      expect(screen.getByText(longDescription[1])).toBeInTheDocument();
    });

    it('handles special characters in description', () => {
      const description = [
        'Description with special chars: !@#$%^&*()',
        'Unicode characters: ñáéíóú',
        'HTML-like content: <script>alert("test")</script>',
      ];

      render(<ResourceDescription description={description} />);

      expect(
        screen.getByText('Description with special chars: !@#$%^&*()')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Unicode characters: ñáéíóú')
      ).toBeInTheDocument();
      expect(
        screen.getByText('HTML-like content: <script>alert("test")</script>')
      ).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading structure', () => {
      const description = ['Test description'];

      render(<ResourceDescription description={description} />);

      const heading = screen.getByRole('heading', { name: 'Description' });
      expect(heading.tagName).toBe('H2');
    });

    it('has proper semantic structure', () => {
      const description = ['Test description'];

      render(<ResourceDescription description={description} />);

      const section = screen
        .getByRole('heading', { name: 'Description' })
        .closest('section');
      expect(section).toBeInTheDocument();
    });

    it('maintains proper text contrast with CSS classes', () => {
      const description = ['Test description'];

      render(<ResourceDescription description={description} />);

      const heading = screen.getByRole('heading', { name: 'Description' });
      expect(heading).toHaveClass('text-gray-900'); // Dark text for good contrast

      const paragraph = screen.getByText('Test description');
      expect(paragraph).toHaveClass('text-gray-600'); // Medium gray for good contrast
    });
  });

  describe('Integration with Real Data', () => {
    it('renders with realistic description data', () => {
      const description = [
        'A comprehensive dataset containing geographic information for the state of Minnesota.',
        'This dataset includes boundaries, administrative divisions, and key geographic features.',
        'Data is sourced from the Minnesota Department of Natural Resources and is updated quarterly.',
      ];

      render(<ResourceDescription description={description} />);

      expect(
        screen.getByRole('heading', { name: 'Description' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          /comprehensive dataset containing geographic information/
        )
      ).toBeInTheDocument();
      expect(
        screen.getByText(/boundaries, administrative divisions/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Minnesota Department of Natural Resources/)
      ).toBeInTheDocument();
    });

    it('handles single paragraph description', () => {
      const description = [
        'This is a single paragraph description for a resource.',
      ];

      render(<ResourceDescription description={description} />);

      expect(
        screen.getByRole('heading', { name: 'Description' })
      ).toBeInTheDocument();
      expect(
        screen.getByText(
          'This is a single paragraph description for a resource.'
        )
      ).toBeInTheDocument();

      const paragraphs = screen.getAllByText(/description/);
      expect(paragraphs).toHaveLength(1);
    });
  });
});
