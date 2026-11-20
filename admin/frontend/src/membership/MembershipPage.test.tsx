import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, expect, it, vi } from 'vitest';
import { MembershipPage } from './MembershipPage';

const resource = {
  id: 'resource-one',
  set_id: 'source' as string | null,
  source_id: 'original-source' as string | null,
  can_associate: true,
  lock_version: 1,
  metadata: { dct_title_s: 'Source map' },
};
const managingSet = {
  set_id: 'target',
  source_id: 'new-source',
  title: 'Target collection',
  lock_version: 2,
};
const json = (value: unknown) => new Response(JSON.stringify(value));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
function setup(
  mode: 'association' | 'representative',
  fail = false,
  record = resource
) {
  const mutations: RequestInit[] = [];
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method) {
      mutations.push(options);
      if (fail && mutations.length === 1) throw new Error('offline');
      return json({});
    }
    if (url.includes('?q='))
      return json({
        items: mode === 'association' ? [managingSet] : [resource],
      });
    return json(mode === 'association' ? record : managingSet);
  });
  vi.stubGlobal('fetch', fetch);
  const router = createMemoryRouter(
    [
      {
        path: '/resources/:resourceId/set',
        element: <MembershipPage mode={mode} />,
      },
      {
        path: '/sets/:setId/representative',
        element: <MembershipPage mode="representative" />,
      },
      { path: '*', element: <h1>Returned to record</h1> },
    ],
    {
      initialEntries: [
        mode === 'association'
          ? '/resources/resource-one/set'
          : '/sets/target/representative',
      ],
    }
  );
  render(<RouterProvider router={router} />);
  return { fetch, mutations };
}

it('confirms explicit reassignment and retries a lost response with the same key', async () => {
  const { mutations } = setup('association', true);
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Choose Target collection (target)',
    })
  );
  expect(
    screen.getByText(/Source: original-source → new-source/)
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Reason'), {
    target: { value: 'Approved move' },
  });
  expect(
    screen.getByRole('button', { name: 'Save association' })
  ).toBeDisabled();
  fireEvent.click(screen.getByLabelText('I confirm this association change.'));
  fireEvent.click(screen.getByRole('button', { name: 'Save association' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveFocus());
  fireEvent.click(screen.getByRole('button', { name: 'Save association' }));
  await screen.findByRole('link', { name: 'View updated record' });
  expect(mutations[0].headers).toEqual(mutations[1].headers);
  expect(JSON.parse(String(mutations[1].body))).toEqual({
    source_set_id: 'source',
    target_set_id: 'target',
    resource_version: 1,
    reason: 'Approved move',
    confirmed: true,
  });
});

it('assigns an unassigned draft with an explicit reason and confirmation', async () => {
  const { mutations } = setup('association', false, {
    ...resource,
    set_id: null,
    source_id: null,
  });
  await screen.findByRole('heading', { name: 'Assign to a Set' });
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Choose Target collection (target)',
    })
  );
  expect(screen.getByText(/Unassigned → new-source/)).toBeVisible();
  const submit = screen.getByRole('button', { name: 'Assign to a Set' });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Reason'), {
    target: { value: 'Cataloged for this collection' },
  });
  fireEvent.click(screen.getByLabelText('I confirm this association change.'));
  fireEvent.click(submit);
  await screen.findByRole('link', { name: 'View updated record' });
  expect(JSON.parse(String(mutations[0].body))).toEqual({
    source_set_id: null,
    target_set_id: 'target',
    resource_version: 1,
    reason: 'Cataloged for this collection',
    confirmed: true,
  });
});

it('hides the form when a direct visit cannot assign the draft', async () => {
  setup('association', false, {
    ...resource,
    set_id: null,
    can_associate: false,
  });
  expect(
    await screen.findByText('Set assignment is unavailable for this Resource.')
  ).toBeVisible();
  expect(
    screen.queryByRole('button', { name: 'Assign to a Set' })
  ).not.toBeInTheDocument();
});

it('clears a representative deliberately and protects unsaved navigation', async () => {
  const { mutations } = setup('representative');
  await screen.findByRole('button', {
    name: 'Choose Source map (resource-one)',
  });
  fireEvent.click(screen.getByLabelText('Clear the representative link'));
  fireEvent.change(screen.getByLabelText('Reason'), {
    target: { value: 'No longer representative' },
  });
  fireEvent.click(screen.getByRole('link', { name: 'Back to record' }));
  await screen.findByRole('button', { name: 'Keep editing' });
  fireEvent.click(screen.getByRole('button', { name: 'Keep editing' }));
  fireEvent.click(screen.getByLabelText('I confirm this association change.'));
  fireEvent.click(screen.getByRole('button', { name: 'Save association' }));
  await screen.findByRole('link', { name: 'View updated record' });
  expect(JSON.parse(String(mutations[0].body))).toEqual({
    resource_id: null,
    lock_version: 2,
    reason: 'No longer representative',
  });
});

it('recovers choice and record reads without bypassing confirmation', async () => {
  const { fetch } = setup('association', true);
  fireEvent.click(
    await screen.findByRole('button', {
      name: 'Choose Target collection (target)',
    })
  );
  fireEvent.change(screen.getByLabelText('Reason'), {
    target: { value: 'Move' },
  });
  fireEvent.click(screen.getByLabelText('I confirm this association change.'));
  fireEvent.click(screen.getByRole('button', { name: 'Save association' }));
  await screen.findByRole('alert');
  fireEvent.click(
    screen.getByRole('button', { name: 'Reload saved version for comparison' })
  );
  await waitFor(() =>
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  );
  expect(
    screen.getByRole('button', { name: 'Save association' })
  ).toBeDisabled();
  fetch.mockRejectedValue(new Error('denied'));
  fireEvent.change(screen.getByLabelText('Search sets'), {
    target: { value: 'unavailable' },
  });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Choices unavailable'
  );
  fireEvent.click(screen.getByRole('link', { name: 'Back to record' }));
  fireEvent.click(
    await screen.findByRole('button', { name: 'Discard and leave' })
  );
  await screen.findByRole('heading', { name: 'Returned to record' });
});
