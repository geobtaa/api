import type { ComponentProps } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AdvancedSearchBuilder } from '../../components/search/AdvancedSearchBuilder';

describe('AdvancedSearchBuilder', () => {
  const renderBuilder = (
    props?: Partial<ComponentProps<typeof AdvancedSearchBuilder>>
  ) => {
    const onApply = vi.fn();
    const onCancel = vi.fn();
    const onReset = vi.fn();

    render(
      <AdvancedSearchBuilder
        clauses={[]}
        onApply={onApply}
        onCancel={onCancel}
        onReset={onReset}
        {...props}
      />
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

  it('calls onApply with sanitized clauses', () => {
    const { onApply } = renderBuilder();

    const valueInput = screen.getByLabelText('Value');
    fireEvent.change(valueInput, { target: { value: '  Water  ' } });

    const fieldSelect = screen.getByLabelText('Field');
    fireEvent.change(fieldSelect, { target: { value: 'dct_description_sm' } });

    fireEvent.click(screen.getByRole('button', { name: /apply/i }));

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
});
