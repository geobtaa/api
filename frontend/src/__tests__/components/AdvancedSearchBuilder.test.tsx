import type { ComponentProps } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import { MemoryRouter } from 'react-router';
import userEvent from '@testing-library/user-event';
import { AdvancedSearchBuilder } from '../../components/search/AdvancedSearchBuilder';

describe('AdvancedSearchBuilder', () => {
  const renderBuilder = (
    props?: Partial<ComponentProps<typeof AdvancedSearchBuilder>>
  ) => {
    const onApply = vi.fn();
    const onCancel = vi.fn();
    const onReset = vi.fn();

    render(
      <MemoryRouter>
        <AdvancedSearchBuilder
          clauses={[]}
          onApply={onApply}
          onCancel={onCancel}
          onReset={onReset}
          {...props}
        />
      </MemoryRouter>
    );

    return { onApply, onCancel, onReset };
  };

  it('renders provided clauses', () => {
    renderBuilder({
      clauses: [
        { op: 'AND', field: 'dct_title_s', q: 'Iowa' },
        { op: 'NOT', field: 'dct_title_s', q: 'Wisconsin' },
      ],
    });

    const valueInputs = screen.getAllByLabelText('Value');
    expect(valueInputs).toHaveLength(2);
    expect((valueInputs[0] as HTMLInputElement).value).toBe('Iowa');
    expect((valueInputs[1] as HTMLInputElement).value).toBe('Wisconsin');
  });

  it('adds a new condition row', () => {
    renderBuilder();

    fireEvent.click(screen.getByRole('button', { name: /add condition/i }));

    const operatorSelects = screen.getAllByLabelText('Operator');
    expect(operatorSelects).toHaveLength(2);
  });

  it('renders the curated advanced search field list', () => {
    renderBuilder();

    const fieldSelect = screen.getByLabelText('Field') as HTMLSelectElement;
    const options = Array.from(fieldSelect.options).map((option) => ({
      value: option.value,
      label: option.text,
    }));

    expect(options).toEqual([
      { value: 'all_fields', label: 'All Fields' },
      { value: 'dct_title_s', label: 'Title' },
      { value: 'dct_accessRights_s', label: 'Access Rights' },
      { value: 'dct_creator_sm', label: 'Creator' },
      { value: 'dct_description_sm', label: 'Description' },
      {
        value: 'b1g_localCollectionLabel_sm',
        label: 'Local Collection',
      },
      { value: 'dct_spatial_sm', label: 'Place' },
      { value: 'schema_provider_s', label: 'Provider' },
      { value: 'dct_publisher_sm', label: 'Publisher' },
      { value: 'gbl_resourceClass_sm', label: 'Resource Class' },
      { value: 'gbl_resourceType_sm', label: 'Resource Type' },
      { value: 'dct_subject_sm', label: 'Subject' },
      { value: 'dcat_theme_sm', label: 'Theme' },
    ]);
  });

  it('calls onApply with sanitized clauses', async () => {
    const user = userEvent.setup();
    const { onApply } = renderBuilder({
      clauses: [{ op: 'AND', field: 'dct_title_s', q: '' }],
    });

    const fieldSelect = screen.getByLabelText('Field');
    await user.selectOptions(fieldSelect, 'dct_description_sm');

    const valueInput = screen.getByLabelText('Value');
    await user.clear(valueInput as HTMLInputElement);
    await user.type(valueInput as HTMLInputElement, '  Water  ');

    await user.click(screen.getByRole('button', { name: /apply/i }));

    expect(onApply).toHaveBeenCalledWith([
      { op: 'AND', field: 'dct_description_sm', q: 'Water' },
    ]);
  });

  it('calls onApply with empty array when no value entered', () => {
    const { onApply } = renderBuilder();

    fireEvent.click(screen.getByRole('button', { name: /apply/i }));

    expect(onApply).toHaveBeenCalledWith([]);
  });

  it('calls onReset handler', () => {
    const { onReset } = renderBuilder({
      clauses: [{ op: 'AND', field: 'dct_title_s', q: 'Iowa' }],
    });

    fireEvent.click(screen.getByRole('button', { name: /reset/i }));

    expect(onReset).toHaveBeenCalled();
  });

  it('calls onCancel handler', () => {
    const { onCancel } = renderBuilder();

    fireEvent.click(screen.getByRole('button', { name: /close/i }));

    expect(onCancel).toHaveBeenCalled();
  });

  describe('Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <MemoryRouter>
          <AdvancedSearchBuilder
            clauses={[]}
            onApply={vi.fn()}
            onCancel={vi.fn()}
            onReset={vi.fn()}
          />
        </MemoryRouter>
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });
  });

  it('focuses first field with preventScroll so page does not jump when user has scrolled', async () => {
    const focusSpy = vi.spyOn(HTMLSelectElement.prototype, 'focus');
    vi.useFakeTimers();

    try {
      renderBuilder();

      await act(async () => {
        vi.advanceTimersByTime(200);
      });

      expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    } finally {
      focusSpy.mockRestore();
      vi.useRealTimers();
    }
  });
});
