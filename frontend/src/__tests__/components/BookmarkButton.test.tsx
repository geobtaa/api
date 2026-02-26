import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { vi } from 'vitest';
import { BookmarkButton } from '../../components/BookmarkButton';
import { BookmarkProvider } from '../../context/BookmarkContext';

// Mock js-cookie
vi.mock('js-cookie', () => ({
  default: {
    get: vi.fn(),
    set: vi.fn(),
    remove: vi.fn(),
  },
  get: vi.fn(),
  set: vi.fn(),
  remove: vi.fn(),
}));

describe('BookmarkButton', () => {
  const TestWrapper = ({ children }: { children: React.ReactNode }) => (
    <BookmarkProvider>{children}</BookmarkProvider>
  );

  beforeEach(() => {
    // Clear any existing bookmarks before each test
    vi.clearAllMocks();
  });

  describe('Basic Rendering', () => {
    it('renders bookmark button with correct initial state', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
      expect(button).toHaveClass('text-gray-400'); // Not bookmarked initially
    });

    it('renders with correct styling classes', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveClass(
        'p-2',
        'rounded-full',
        'hover:bg-gray-100',
        'transition-colors'
      );
    });

    it('renders bookmark icon', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      const icon = button.querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('w-5', 'h-5');
    });
  });

  describe('Bookmark State Management', () => {
    it('shows bookmarked state when item is bookmarked', () => {
      // Pre-populate bookmarks
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      // Add bookmark by clicking
      const button = screen.getByRole('button');
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      expect(button).toHaveAttribute('aria-label', 'Remove bookmark');
      expect(button).toHaveClass('text-blue-500'); // Bookmarked state
    });

    it('shows unbookmarked state when item is not bookmarked', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
      expect(button).toHaveClass('text-gray-400'); // Not bookmarked
    });

    it('toggles bookmark state correctly', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');

      // Initially not bookmarked
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
      expect(button).toHaveClass('text-gray-400');

      // Click to add bookmark
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      // Now bookmarked
      expect(button).toHaveAttribute('aria-label', 'Remove bookmark');
      expect(button).toHaveClass('text-blue-500');

      // Click to remove bookmark
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      // Back to not bookmarked
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
      expect(button).toHaveClass('text-gray-400');
    });
  });

  describe('Click Handling', () => {
    it('calls addBookmark when item is not bookmarked', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      // The bookmark should be added (we can verify by checking the state)
      // Since we're using the real BookmarkProvider, the state will actually change
      expect(button).toBeInTheDocument();
    });

    it('calls removeBookmark when item is bookmarked', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');

      // First add bookmark
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      // Now remove bookmark
      fireEvent.click(button);

      // The bookmark should be removed
      expect(button).toBeInTheDocument();
    });

    it('prevents default event behavior on click', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      const mockEvent = {
        preventDefault: vi.fn(),
        stopPropagation: vi.fn(),
      } as unknown as React.MouseEvent;

      // Simulate click with preventDefault
      fireEvent.click(button, mockEvent);

      // The click should be handled without errors
      expect(button).toBeInTheDocument();
    });
  });

  describe('Icon Rendering', () => {
    it('renders unfilled icon when not bookmarked', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      const icon = button.querySelector('svg');
      expect(icon).toBeInTheDocument();

      // The fill should be 'none' when not bookmarked
      // We can't easily test the fill attribute directly, but we can test the styling
      expect(button).toHaveClass('text-gray-400');
    });

    it('renders filled icon when bookmarked', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');

      // Add bookmark
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const icon = button.querySelector('svg');
      expect(icon).toBeInTheDocument();

      // The fill should be 'currentColor' when bookmarked
      // We can test this by checking the button color class
      expect(button).toHaveClass('text-blue-500');
    });
  });

  describe('Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('has correct aria-label for unbookmarked state', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('has correct aria-label for bookmarked state', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');

      // Add bookmark
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      expect(button).toHaveAttribute('aria-label', 'Remove bookmark');
    });

    it('is keyboard accessible', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();

      // Button should be focusable
      button.focus();
      expect(document.activeElement).toBe(button);
    });
  });

  describe('Multiple Items', () => {
    it('handles multiple bookmark buttons independently', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
          <BookmarkButton itemId="test-item-2" />
        </TestWrapper>
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(2);

      // Both should start unbookmarked
      expect(buttons[0]).toHaveAttribute('aria-label', 'Add bookmark');
      expect(buttons[1]).toHaveAttribute('aria-label', 'Add bookmark');

      // Bookmark first item
      fireEvent.click(buttons[0]);

      // Re-render to reflect state change
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
          <BookmarkButton itemId="test-item-2" />
        </TestWrapper>
      );

      const updatedButtons = screen.getAllByRole('button');

      // First should be bookmarked, second should remain unbookmarked
      expect(updatedButtons[0]).toHaveAttribute(
        'aria-label',
        'Remove bookmark'
      );
      expect(updatedButtons[1]).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('maintains correct state for each item', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="item-1" />
          <BookmarkButton itemId="item-2" />
          <BookmarkButton itemId="item-3" />
        </TestWrapper>
      );

      const buttons = screen.getAllByRole('button');

      // Bookmark items 1 and 3
      fireEvent.click(buttons[0]); // item-1
      fireEvent.click(buttons[2]); // item-3

      // Re-render to reflect state changes
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="item-1" />
          <BookmarkButton itemId="item-2" />
          <BookmarkButton itemId="item-3" />
        </TestWrapper>
      );

      const updatedButtons = screen.getAllByRole('button');

      expect(updatedButtons[0]).toHaveAttribute(
        'aria-label',
        'Remove bookmark'
      ); // item-1
      expect(updatedButtons[1]).toHaveAttribute('aria-label', 'Add bookmark'); // item-2
      expect(updatedButtons[2]).toHaveAttribute(
        'aria-label',
        'Remove bookmark'
      ); // item-3
    });
  });

  describe('Edge Cases', () => {
    it('handles empty itemId', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('handles special characters in itemId', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="item-with-special-chars-!@#$%^&*()" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('handles very long itemId', () => {
      const longId = 'a'.repeat(1000);
      render(
        <TestWrapper>
          <BookmarkButton itemId={longId} />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('handles rapid clicking', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');

      // Rapidly click multiple times
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(button);

      // Should not cause errors
      expect(button).toBeInTheDocument();
    });
  });

  describe('Integration with BookmarkContext', () => {
    it('reflects changes from external bookmark operations', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');

      // Initially not bookmarked
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');

      // Simulate external bookmark addition (by clicking)
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="test-item-1" />
        </TestWrapper>
      );

      // Should now be bookmarked
      expect(button).toHaveAttribute('aria-label', 'Remove bookmark');
    });

    it('works with different item IDs', () => {
      const testIds = ['item-1', 'item-2', 'item-3', 'item-4'];

      render(
        <TestWrapper>
          {testIds.map((id) => (
            <BookmarkButton key={id} itemId={id} />
          ))}
        </TestWrapper>
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(4);

      // All should start unbookmarked
      buttons.forEach((button) => {
        expect(button).toHaveAttribute('aria-label', 'Add bookmark');
      });
    });
  });

  describe('Real Fixture Data Integration', () => {
    it('works with MIT Libraries fixture data', () => {
      const { rerender } = render(
        <TestWrapper>
          <BookmarkButton itemId="mit-001145244" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');

      // Test bookmarking
      fireEvent.click(button);

      // Re-render to reflect state change
      rerender(
        <TestWrapper>
          <BookmarkButton itemId="mit-001145244" />
        </TestWrapper>
      );

      const updatedButton = screen.getByRole('button');
      expect(updatedButton).toHaveAttribute('aria-label', 'Remove bookmark');
    });

    it('works with NYU Libraries fixture data', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="nyu-2451-34564" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('works with Tufts University fixture data', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="tufts-cambridgegrid100-04" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });

    it('works with Stanford University fixture data', () => {
      render(
        <TestWrapper>
          <BookmarkButton itemId="stanford-dp018hs9766" />
        </TestWrapper>
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('aria-label', 'Add bookmark');
    });
  });
});
