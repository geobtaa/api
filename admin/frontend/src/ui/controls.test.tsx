import { createRef } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ActionButton, SelectControl, TextArea, TextInput } from './controls';

it('preserves native labels, validation, error descriptions, and focus refs', () => {
  const title = createRef<HTMLInputElement>();
  render(
    <form aria-label="Example editor">
      <label htmlFor="title">Title</label>
      <TextInput
        id="title"
        ref={title}
        required
        aria-invalid="true"
        aria-describedby="title-error"
      />
      <p id="title-error">A title is required.</p>
      <label htmlFor="description">Description</label>
      <TextArea
        id="description"
        name="description"
        defaultValue="Saved description"
        readOnly
      />
      <label htmlFor="state">State</label>
      <SelectControl id="state" name="state" defaultValue="draft">
        <option value="draft">Draft</option>
        <option value="active">Active</option>
      </SelectControl>
    </form>
  );
  expect(screen.getByRole('textbox', { name: 'Title' })).toBeRequired();
  expect(title.current).toBeInvalid();
  expect(title.current).toHaveAccessibleDescription('A title is required.');
  title.current?.focus();
  expect(title.current).toHaveFocus();
  fireEvent.change(title.current!, { target: { value: 'Updated title' } });
  expect(title.current?.checkValidity()).toBe(true);
  expect(screen.getByRole('textbox', { name: 'Description' })).toHaveAttribute(
    'readonly'
  );
  fireEvent.change(screen.getByRole('combobox', { name: 'State' }), {
    target: { value: 'active' },
  });
  expect(screen.getByRole('combobox', { name: 'State' })).toHaveValue('active');
});

it('preserves checkbox, radio, file, and disabled button behavior', () => {
  const save = vi.fn();
  const fileChanged = vi.fn();
  render(
    <>
      <label>
        <TextInput type="checkbox" />
        Confirm change
      </label>
      <label>
        <TextInput type="radio" name="mode" value="create" />
        Create
      </label>
      <label>
        Import file
        <TextInput type="file" accept=".csv" onChange={fileChanged} />
      </label>
      <ActionButton disabled onClick={save}>
        Save
      </ActionButton>
    </>
  );
  fireEvent.click(screen.getByRole('checkbox', { name: 'Confirm change' }));
  expect(
    screen.getByRole('checkbox', { name: 'Confirm change' })
  ).toBeChecked();
  fireEvent.click(screen.getByRole('radio', { name: 'Create' }));
  expect(screen.getByRole('radio', { name: 'Create' })).toBeChecked();
  const file = new File(['title\nExample'], 'resources.csv', {
    type: 'text/csv',
  });
  fireEvent.change(screen.getByLabelText('Import file'), {
    target: { files: [file] },
  });
  expect(fileChanged).toHaveBeenCalledOnce();
  expect(
    (screen.getByLabelText('Import file') as HTMLInputElement).files?.[0]
  ).toBe(file);
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(save).not.toHaveBeenCalled();
});
