import { render, screen } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import userEvent from '@testing-library/user-event';
import { SortControl } from '../../components/search/SortControl';

// Real sort options based on typical search functionality
const mockSortOptions = [
  {
    id: 'relevance',
    label: 'Relevance',
    url: '/search?sort=relevance',
  },
  {
    id: 'title_asc',
    label: 'Title (A-Z)',
    url: '/search?sort=title_asc',
  },
  {
    id: 'title_desc',
    label: 'Title (Z-A)',
    url: '/search?sort=title_desc',
  },
  {
    id: 'date_asc',
    label: 'Date (Oldest First)',
    url: '/search?sort=date_asc',
  },
  {
    id: 'date_desc',
    label: 'Date (Newest First)',
    url: '/search?sort=date_desc',
  },
  {
    id: 'publisher_asc',
    label: 'Publisher (A-Z)',
    url: '/search?sort=publisher_asc',
  },
];

describe('SortControl', () => {
  const mockOnSortChange = vi.fn();

  beforeEach(() => {
    mockOnSortChange.mockClear();
  });

  describe('Basic Rendering', () => {
    it('renders with sort options', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      // Check for the label
      expect(screen.getByText('Sort by:')).toBeInTheDocument();

      // Check for the select element
      const select = screen.getByRole('combobox');
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue('relevance');

      // Check for all options
      mockSortOptions.forEach((option) => {
        expect(
          screen.getByRole('option', { name: option.label })
        ).toBeInTheDocument();
      });
    });

    it('renders with correct current sort value', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="title_asc"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');
      expect(select).toHaveValue('title_asc');
    });

    it('renders the chevron down icon', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      // The chevron icon should be present (it's an SVG)
      const chevronIcon = document.querySelector('svg');
      expect(chevronIcon).toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    it('returns null when options is null', () => {
      const { container } = render(
        <SortControl
          options={null as any}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    it('returns null when options is undefined', () => {
      const { container } = render(
        <SortControl
          options={undefined as any}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    it('returns null when options array is empty', () => {
      const { container } = render(
        <SortControl
          options={[]}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('User Interactions', () => {
    it('calls onSortChange when user selects a different option', async () => {
      const user = userEvent.setup();

      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');
      await user.selectOptions(select, 'title_asc');

      expect(mockOnSortChange).toHaveBeenCalledTimes(1);
      expect(mockOnSortChange).toHaveBeenCalledWith('title_asc');
    });

    it('calls onSortChange with correct value for each option', async () => {
      const user = userEvent.setup();

      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');

      // Test each option
      for (const option of mockSortOptions) {
        await user.selectOptions(select, option.id);
        expect(mockOnSortChange).toHaveBeenCalledWith(option.id);
      }

      expect(mockOnSortChange).toHaveBeenCalledTimes(mockSortOptions.length);
    });

    it('updates the select value when currentSort prop changes', () => {
      const { rerender } = render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      let select = screen.getByRole('combobox');
      expect(select).toHaveValue('relevance');

      // Change the currentSort prop
      rerender(
        <SortControl
          options={mockSortOptions}
          currentSort="date_desc"
          onSortChange={mockOnSortChange}
        />
      );

      select = screen.getByRole('combobox');
      expect(select).toHaveValue('date_desc');
    });
  });

  describe('Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('has proper label association', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const label = screen.getByText('Sort by:');
      const select = screen.getByRole('combobox');

      expect(label).toHaveAttribute('for', 'sort-select');
      expect(select).toHaveAttribute('id', 'sort-select');
    });

    it('has accessible option labels', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      // Check that each option has the correct accessible name
      mockSortOptions.forEach((option) => {
        const optionElement = screen.getByRole('option', {
          name: option.label,
        });
        expect(optionElement).toHaveValue(option.id);
        expect(optionElement).toHaveTextContent(option.label);
      });
    });

    it('has proper ARIA attributes', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');
      expect(select).toHaveAttribute('id', 'sort-select');
    });
  });

  describe('Styling and Visual Elements', () => {
    it('applies correct CSS classes to the container', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const container = screen.getByText('Sort by:').closest('div');
      expect(container).toHaveClass('flex', 'items-center', 'gap-2');
    });

    it('applies correct CSS classes to the select element', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');
      expect(select).toHaveClass(
        'appearance-none',
        'bg-white',
        'border',
        'border-gray-300',
        'rounded-md',
        'py-1.5',
        'pl-3',
        'pr-8',
        'text-sm',
        'leading-6',
        'text-gray-900',
        'focus:outline-none',
        'focus:ring-2',
        'focus:ring-blue-500'
      );
    });

    it('applies correct CSS classes to the label', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const label = screen.getByText('Sort by:');
      expect(label).toHaveClass('text-sm', 'text-gray-600');
    });

    it('positions the chevron icon correctly', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const chevronIcon = document.querySelector('svg');
      expect(chevronIcon).toHaveClass(
        'absolute',
        'right-2',
        'top-1/2',
        '-translate-y-1/2',
        'h-4',
        'w-4',
        'text-gray-500',
        'pointer-events-none'
      );
    });
  });

  describe('Edge Cases', () => {
    it('handles single option correctly', () => {
      const singleOption = [mockSortOptions[0]];

      render(
        <SortControl
          options={singleOption}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');
      expect(select).toHaveValue('relevance');
      expect(
        screen.getByRole('option', { name: 'Relevance' })
      ).toBeInTheDocument();
    });

    it('handles currentSort not matching any option', () => {
      render(
        <SortControl
          options={mockSortOptions}
          currentSort="nonexistent_sort"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');
      // When currentSort doesn't match any option, the select defaults to the first option
      expect(select).toHaveValue('relevance');
    });

    it('handles options with special characters in labels', () => {
      const specialOptions = [
        {
          id: 'special_sort',
          label: 'Special Sort (with parentheses)',
          url: '/search?sort=special_sort',
        },
        {
          id: 'another_sort',
          label: 'Another Sort & More',
          url: '/search?sort=another_sort',
        },
      ];

      render(
        <SortControl
          options={specialOptions}
          currentSort="special_sort"
          onSortChange={mockOnSortChange}
        />
      );

      expect(
        screen.getByRole('option', { name: 'Special Sort (with parentheses)' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('option', { name: 'Another Sort & More' })
      ).toBeInTheDocument();
    });

    it('handles very long option labels', () => {
      const longLabelOptions = [
        {
          id: 'long_sort',
          label:
            'This is a very long sort option label that might wrap or cause layout issues',
          url: '/search?sort=long_sort',
        },
      ];

      render(
        <SortControl
          options={longLabelOptions}
          currentSort="long_sort"
          onSortChange={mockOnSortChange}
        />
      );

      expect(
        screen.getByRole('option', { name: longLabelOptions[0].label })
      ).toBeInTheDocument();
    });
  });

  describe('Component Integration', () => {
    it('works with different currentSort values', () => {
      const testCases = [
        { currentSort: 'relevance', expectedValue: 'relevance' },
        { currentSort: 'title_asc', expectedValue: 'title_asc' },
        { currentSort: 'date_desc', expectedValue: 'date_desc' },
        { currentSort: '', expectedValue: 'relevance' }, // Empty string defaults to first option
        { currentSort: '0', expectedValue: 'relevance' }, // Non-existent option defaults to first option
      ];

      testCases.forEach(({ currentSort, expectedValue }) => {
        const { unmount } = render(
          <SortControl
            options={mockSortOptions}
            currentSort={currentSort}
            onSortChange={mockOnSortChange}
          />
        );

        const select = screen.getByRole('combobox');
        expect(select).toHaveValue(expectedValue);

        unmount();
      });
    });

    it('maintains focus behavior during interactions', async () => {
      const user = userEvent.setup();

      render(
        <SortControl
          options={mockSortOptions}
          currentSort="relevance"
          onSortChange={mockOnSortChange}
        />
      );

      const select = screen.getByRole('combobox');

      // Focus the select
      await user.click(select);
      expect(select).toHaveFocus();

      // Change selection
      await user.selectOptions(select, 'title_asc');

      // Select should still be focused
      expect(select).toHaveFocus();
      expect(mockOnSortChange).toHaveBeenCalledWith('title_asc');
    });
  });
});
