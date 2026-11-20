import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AssigneeSelect } from './AssigneeSelect';

afterEach(() => vi.unstubAllGlobals());

it('discards the selected assignee together with the rest of a reset draft', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: true,
      json: async () => [
        { actor_id: 'original', display_name: 'Original staff' },
        { actor_id: 'other', display_name: 'Other staff' },
      ],
    }))
  );
  let submitted: FormData | undefined;
  render(
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submitted = new FormData(event.currentTarget);
      }}
    >
      <AssigneeSelect initial="original" setId="maps" />
      <button type="reset">Discard changes</button>
      <button type="submit">Save</button>
    </form>
  );
  const select = await screen.findByRole('combobox', { name: 'Assignee' });
  fireEvent.change(select, { target: { value: 'other' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(submitted?.get('assignee_id')).toBe('other');
  fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
  await waitFor(() => expect(select).toHaveValue('original'));
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  expect(submitted?.get('assignee_id')).toBe('original');
});
