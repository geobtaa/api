import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';
import btaaLogo from './assets/btaa-logo.png?inline';

describe('App', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens the metadata workspace without deferred work features', () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: 'Workspace' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: 'Big Ten Academic Alliance' })
    ).toHaveAttribute('src', btaaLogo);
    expect(
      screen.getByRole('link', { name: 'GEOMG Admin home' })
    ).toHaveTextContent('Metadata administration');
    expect(screen.getByRole('search')).toBeInTheDocument();
    for (const name of ['Work', 'Jobs', 'Work Queue', 'Calendar']) {
      expect(screen.queryByRole('link', { name })).not.toBeInTheDocument();
    }
    expect(
      screen.queryByRole('option', { name: 'Work' })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Work to follow up')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    expect(
      screen.getByRole('navigation', { name: 'Account and system' })
    ).toBeInTheDocument();
  });

  it('opens the CSV importer from an old Resource import bookmark and keeps its Set', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          total: 1,
          items: [{ set_id: 'maps', title: 'Maps', status: 'active' }],
        }),
      })
    );
    render(
      <MemoryRouter initialEntries={['/resources/import?set_id=maps']}>
        <App />
      </MemoryRouter>
    );
    expect(
      await screen.findByRole('heading', { name: 'Resources CSV import' })
    ).toBeInTheDocument();
    await screen.findByRole('option', { name: 'Maps' });
    expect(screen.getByLabelText('Set')).toHaveValue('maps');
    expect(screen.getByLabelText('CSV file')).toBeInTheDocument();
  });

  it('renders the system page', () => {
    render(
      <MemoryRouter initialEntries={['/system']}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: 'System endpoints' })
    ).toBeInTheDocument();
    expect(screen.getByText('/api/v1/health')).toBeInTheDocument();
    expect(screen.getByText('/api/v1/ready')).toBeInTheDocument();
  });

  it('opens a Source named new through its direct detail route', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url.includes('/admin/contracts/')
            ? {
                create: false,
                update: false,
                activity_read: false,
                resource_read: false,
              }
            : {
                source_id: 'new',
                title: 'New inventory source',
                lock_version: 1,
              },
      }))
    );
    render(
      <MemoryRouter initialEntries={['/sources/~bmV3']}>
        <App />
      </MemoryRouter>
    );
    expect(
      await screen.findByRole('heading', { name: 'New inventory source' })
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sources' })).toHaveAttribute(
      'href',
      '/sources'
    );
    expect(screen.getByRole('link', { name: 'Sources' })).toHaveAttribute(
      'aria-current',
      'page'
    );
    expect(screen.getByRole('link', { name: 'Home' })).not.toHaveAttribute(
      'aria-current'
    );
  });

  it('shows the authenticated development actor', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          authenticated: true,
          actor: {
            actor_id: 'local-developer',
            kind: 'user',
            display_name: 'Local Developer',
            email: 'developer@localhost',
            permissions: ['admin.session:read'],
            set_ids: null,
          },
        }),
      })
    );

    render(
      <MemoryRouter initialEntries={['/access']}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole('heading', { name: 'Local Developer' })
    ).toBeInTheDocument();
    expect(screen.getByText('admin.session:read')).toBeInTheDocument();
  });

  it.each([true, false])(
    'shows a simple alpha role and reserves account setup for admins (%s)',
    async (admin) => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          headers: new Headers({ 'X-GEOMG-Auth-Mode': 'local-password' }),
          json: async () => ({
            authenticated: true,
            actor: {
              kind: 'user',
              actor_id: 'fixture',
              email: 'tester@example.edu',
              display_name: 'Tester',
              permissions: admin
                ? ['identity:manage', 'resources:read']
                : ['resources:read'],
              set_ids: null,
            },
          }),
        })
      );
      render(
        <MemoryRouter initialEntries={['/access']}>
          <App />
        </MemoryRouter>
      );
      expect(
        await screen.findByText(admin ? 'Administrator' : 'Catalog editor')
      ).toBeVisible();
      expect(
        screen.getByRole('link', { name: 'Open catalog' })
      ).toHaveAttribute('href', '/resources');
      expect(screen.queryByText('resources:read')).toBeNull();
      if (admin) expect(screen.getByText('Tester accounts')).toBeVisible();
      else expect(screen.queryByText('Tester accounts')).toBeNull();
    }
  );

  it('shows explicit fallbacks for optional actor details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          authenticated: true,
          actor: {
            actor_id: 'limited-actor',
            kind: 'service_account',
            display_name: 'Limited client',
            email: null,
            permissions: [],
            set_ids: [],
          },
        }),
      })
    );

    render(
      <MemoryRouter initialEntries={['/access']}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole('heading', { name: 'Limited client' })
    ).toBeInTheDocument();
    expect(screen.getByText('Not supplied')).toBeInTheDocument();
    expect(screen.getByText('No permissions assigned')).toBeInTheDocument();
  });

  it('explains when authentication is required', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401 })
    );

    render(
      <MemoryRouter initialEntries={['/access']}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole('heading', {
        name: 'This administrative route is protected.',
      })
    ).toBeInTheDocument();
  });

  it('reports an unavailable session API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));

    render(
      <MemoryRouter initialEntries={['/access']}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole('heading', {
        name: 'Session status could not be loaded.',
      })
    ).toBeInTheDocument();
  });

  it('reports an unsuccessful session response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 503 })
    );

    render(
      <MemoryRouter initialEntries={['/access']}>
        <App />
      </MemoryRouter>
    );

    expect(
      await screen.findByRole('heading', {
        name: 'Session status could not be loaded.',
      })
    ).toBeInTheDocument();
  });

  it.each([
    '/missing',
    '/work',
    '/work?view=calendar',
    '/work/periods/new',
    '/tasks/new',
    '/tasks/task-1',
    '/jobs',
    '/jobs/job-1',
    '/sets/maps/maintenance',
  ])('renders the not-found page for %s', (path) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    );

    expect(
      screen.getByRole('heading', { name: 'Page not found' })
    ).toBeInTheDocument();
  });
});
