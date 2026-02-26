import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { Pagination } from '../../components/Pagination';

describe('Pagination Component', () => {
  const mockOnPageChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('renders pagination with current page and total pages', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('highlights the current page', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const currentPageButton = screen.getByText('3');
      expect(currentPageButton).toHaveClass('bg-blue-700', 'text-white');
    });

    it('renders navigation arrows', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      // Check for navigation buttons by their position (first and last buttons)
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThanOrEqual(2);

      // First button should be previous (disabled on page 1)
      expect(buttons[0]).toBeDisabled();
      // Last button should be next
      expect(buttons[buttons.length - 1]).not.toBeDisabled();
    });
  });

  describe('Navigation Buttons', () => {
    it('disables previous button on first page', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const prevButton = screen.getAllByRole('button')[0]; // First button is previous
      expect(prevButton).toBeDisabled();
    });

    it('enables previous button when not on first page', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const prevButton = screen.getAllByRole('button')[0]; // First button is previous
      expect(prevButton).not.toBeDisabled();
    });

    it('disables next button on last page', () => {
      render(
        <Pagination
          currentPage={5}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const buttons = screen.getAllByRole('button');
      const nextButton = buttons[buttons.length - 1]; // Last button is next
      expect(nextButton).toBeDisabled();
    });

    it('enables next button when not on last page', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const buttons = screen.getAllByRole('button');
      const nextButton = buttons[buttons.length - 1]; // Last button is next
      expect(nextButton).not.toBeDisabled();
    });

    it('calls onPageChange when previous button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const prevButton = screen.getAllByRole('button')[0];
      await user.click(prevButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(2);
    });

    it('calls onPageChange when next button is clicked', async () => {
      const user = userEvent.setup();
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const buttons = screen.getAllByRole('button');
      const nextButton = buttons[buttons.length - 1];
      await user.click(nextButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(4);
    });
  });

  describe('Page Number Display Logic', () => {
    it('shows all pages when total pages is 5 or less', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.queryByText('...')).not.toBeInTheDocument();
    });

    it('shows first 5 pages when current page is in the beginning', () => {
      render(
        <Pagination
          currentPage={2}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('...')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('shows last 5 pages when current page is near the end', () => {
      render(
        <Pagination
          currentPage={9}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('...')).toBeInTheDocument();
      expect(screen.getByText('6')).toBeInTheDocument();
      expect(screen.getByText('7')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('9')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('shows 5 pages centered around current page when in the middle', () => {
      render(
        <Pagination
          currentPage={5}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      const ellipsisElements = screen.getAllByText('...');
      expect(ellipsisElements).toHaveLength(2);
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('6')).toBeInTheDocument();
      expect(screen.getByText('7')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });
  });

  describe('Ellipsis Display Logic', () => {
    it('shows ellipsis after first page when there is a gap', () => {
      render(
        <Pagination
          currentPage={5}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      const ellipsisElements = screen.getAllByText('...');
      expect(ellipsisElements).toHaveLength(2);
    });

    it('does not show ellipsis after first page when pages are consecutive', () => {
      render(
        <Pagination
          currentPage={2}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      const ellipsisElements = screen.getAllByText('...');
      expect(ellipsisElements).toHaveLength(1);
    });

    it('does not show ellipsis before last page when pages are consecutive', () => {
      render(
        <Pagination
          currentPage={9}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      const ellipsisElements = screen.getAllByText('...');
      expect(ellipsisElements).toHaveLength(1);
    });

    it('shows ellipsis before last page when there is a gap', () => {
      render(
        <Pagination
          currentPage={5}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      const ellipsisElements = screen.getAllByText('...');
      expect(ellipsisElements).toHaveLength(2);
    });
  });

  describe('Page Click Handling', () => {
    it('calls onPageChange when a page number is clicked', async () => {
      const user = userEvent.setup();
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const pageButton = screen.getByText('3');
      await user.click(pageButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(3);
    });

    it('calls onPageChange when first page is clicked', async () => {
      const user = userEvent.setup();
      render(
        <Pagination
          currentPage={5}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      const firstPageButton = screen.getByText('1');
      await user.click(firstPageButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(1);
    });

    it('calls onPageChange when last page is clicked', async () => {
      const user = userEvent.setup();
      render(
        <Pagination
          currentPage={1}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      const lastPageButton = screen.getByText('10');
      await user.click(lastPageButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(10);
    });
  });

  describe('Edge Cases', () => {
    it('handles single page correctly', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={1}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.queryByText('...')).not.toBeInTheDocument();

      const buttons = screen.getAllByRole('button');
      expect(buttons[0]).toBeDisabled(); // Previous button
      expect(buttons[buttons.length - 1]).toBeDisabled(); // Next button
    });

    it('handles two pages correctly', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={2}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.queryByText('...')).not.toBeInTheDocument();
    });

    it('handles current page at the very beginning', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('...')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('handles current page at the very end', () => {
      render(
        <Pagination
          currentPage={10}
          totalPages={10}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('...')).toBeInTheDocument();
      expect(screen.getByText('6')).toBeInTheDocument();
      expect(screen.getByText('7')).toBeInTheDocument();
      expect(screen.getByText('8')).toBeInTheDocument();
      expect(screen.getByText('9')).toBeInTheDocument();
      expect(screen.getByText('10')).toBeInTheDocument();
    });

    it('handles large number of pages correctly', () => {
      render(
        <Pagination
          currentPage={50}
          totalPages={100}
          onPageChange={mockOnPageChange}
        />
      );

      expect(screen.getByText('1')).toBeInTheDocument();
      const ellipsisElements = screen.getAllByText('...');
      expect(ellipsisElements).toHaveLength(2);
      expect(screen.getByText('48')).toBeInTheDocument();
      expect(screen.getByText('49')).toBeInTheDocument();
      expect(screen.getByText('50')).toBeInTheDocument();
      expect(screen.getByText('51')).toBeInTheDocument();
      expect(screen.getByText('52')).toBeInTheDocument();
      expect(screen.getByText('100')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('previous button has accessible name for screen readers and Lighthouse', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const prevButton = screen.getByRole('button', { name: 'Previous page' });
      expect(prevButton).toBeInTheDocument();
    });

    it('next button has accessible name for screen readers and Lighthouse', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const nextButton = screen.getByRole('button', { name: 'Next page' });
      expect(nextButton).toBeInTheDocument();
    });

    it('has proper button roles', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });

    it('applies proper disabled styling to navigation buttons', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const prevButton = screen.getAllByRole('button')[0];
      expect(prevButton).toHaveClass(
        'disabled:opacity-50',
        'disabled:cursor-not-allowed'
      );
    });

    it('applies hover effects to clickable buttons', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const pageButton = screen.getByText('2');
      expect(pageButton).toHaveClass('hover:bg-gray-100');
    });
  });

  describe('Styling and CSS Classes', () => {
    it('applies correct styling to current page button', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const currentPageButton = screen.getByText('3');
      expect(currentPageButton).toHaveClass('bg-blue-700', 'text-white');
    });

    it('applies correct styling to non-current page buttons', () => {
      render(
        <Pagination
          currentPage={3}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const nonCurrentPageButton = screen.getByText('2');
      expect(nonCurrentPageButton).toHaveClass('hover:bg-gray-100');
      expect(nonCurrentPageButton).not.toHaveClass('bg-blue-700', 'text-white');
    });

    it('applies correct container styling', () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
        />
      );

      const paginationContainer = container.firstChild;
      expect(paginationContainer).toHaveClass(
        'flex',
        'justify-center',
        'items-center',
        'space-x-2',
        'mt-8'
      );
    });
  });
});
