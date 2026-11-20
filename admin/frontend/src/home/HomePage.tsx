import { showWorkManagement } from '../config/features';
import { useEffect, useState, type ReactNode } from 'react';
import { Link, useNavigate } from 'react-router';
import { ApiError, request, type Page } from '../api';
import type { Task } from '../work/api';
import { ActionButton, SelectControl, TextInput } from '../ui/controls';
import { ui } from '../ui/styles';

const workAreas = [
  {
    title: 'Resources',
    to: '/resources',
    description: 'Find, edit, and preview descriptive metadata.',
    links: [{ label: 'Import CSV', to: '/resources/csv' }],
  },
  {
    title: 'Sources',
    to: '/sources',
    description: 'Browse originating collections and record work completed.',
    links: [{ label: 'Browse Sources', to: '/sources' }],
  },
  {
    title: 'Sets',
    to: '/sets',
    description: 'Browse Source-owned groups and their acquisition context.',
    links: [
      { label: 'Browse Sets', to: '/sets' },
      { label: 'Create Set', to: '/sets/new' },
    ],
  },
];
if (showWorkManagement) {
  workAreas.push({
    title: 'Work',
    to: '/work',
    description:
      'Plan recurring work and report completed reviews and ingests.',
    links: [
      { label: 'Work Queue', to: '/work' },
      { label: 'Calendar', to: '/work?view=calendar' },
    ],
  });
}

export function HomePage() {
  const navigate = useNavigate();
  const [area, setArea] = useState('/resources');
  return (
    <main id="main-content" className={ui.page}>
      <p className={ui.kicker}>Metadata administration</p>
      <h1>Workspace</h1>
      <p className={ui.intro}>Find and manage Resources, Sources, and Sets.</p>

      <form
        role="search"
        aria-label="Search metadata workspace"
        className={`${ui.panel} mb-6 grid items-end gap-3 sm:grid-cols-[10rem_minmax(0,1fr)_auto]`}
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          const q = String(data.get('q') ?? '').trim();
          navigate(`${area}?${new URLSearchParams({ q })}`);
        }}
      >
        <label className={ui.field}>
          Search in
          <SelectControl
            name="area"
            value={area}
            onChange={(event) => setArea(event.target.value)}
          >
            {workAreas.map(({ title, to }) => (
              <option key={to} value={to}>
                {title}
              </option>
            ))}
          </SelectControl>
        </label>
        <label className={ui.field}>
          {area === '/sets' ? 'Title, ID, or legacy code' : 'Title or ID'}
          <TextInput
            name="q"
            type="search"
            maxLength={200}
            placeholder="Find a record…"
          />
        </label>
        <ActionButton className={ui.primary} type="submit">
          Search
        </ActionButton>
      </form>

      <section
        aria-label="Workspace areas"
        className={`mb-8 grid gap-4 sm:grid-cols-2 ${showWorkManagement ? 'xl:grid-cols-4' : 'lg:grid-cols-3'}`}
      >
        {workAreas.map((area) => (
          <article className={ui.panel} key={area.title}>
            <h2 className="mb-2">
              <Link className="hover:underline" to={area.to}>
                {area.title} <span aria-hidden="true">→</span>
              </Link>
            </h2>
            <p className="text-sm text-text-secondary">{area.description}</p>
            <div className="flex flex-wrap gap-x-5 gap-y-2">
              {area.links.map((link) => (
                <Link
                  className="inline-flex min-h-8 items-center text-sm font-medium hover:underline"
                  key={link.label}
                  to={link.to}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </article>
        ))}
      </section>

      {showWorkManagement && <WorkOverview />}
    </main>
  );
}

function WorkOverview() {
  return (
    <>
      <div className="mb-4">
        <h2 className="mb-1">Work to follow up</h2>
        <p className="mb-0 text-sm text-text-secondary">
          Pending Tasks within your access, due today or earlier. Calendar and
          completed work are available in Work. Dates use UTC.
        </p>
      </div>
      <div className="grid items-start gap-4 md:grid-cols-3">
        <DueWork family="review" title="Reviews due" />
        <DueWork family="ingest" title="Ingests due" />
        <WorkPanel<Job>
          title="Recent validation jobs"
          url="/api/v1/admin/jobs?offset=0&limit=5"
          to="/jobs"
          viewLabel="View all jobs"
          empty="No validation jobs yet. Select saved drafts in Resources to validate them."
        >
          {(page) => (
            <>
              <p className="text-sm text-text-secondary">
                Latest {page.items.length} of {page.total.toLocaleString()} jobs
                · newest first
              </p>
              <ul className="divide-y divide-border">
                {page.items.map((job) => (
                  <li key={job.job_id} className="py-3 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link
                        className="text-sm font-semibold hover:underline"
                        to={`/jobs/${encodeURIComponent(job.job_id)}`}
                      >
                        Validation results{' '}
                        <span className="sr-only">for {job.job_id}</span>
                      </Link>
                      <span className={ui.badge}>
                        {job.state.replaceAll('_', ' ')}
                      </span>
                    </div>
                    <time
                      className="mt-1 block text-xs text-text-secondary"
                      dateTime={job.created_at}
                    >
                      {new Date(job.created_at).toLocaleString()}
                    </time>
                  </li>
                ))}
              </ul>
            </>
          )}
        </WorkPanel>
      </div>
    </>
  );
}

type Job = {
  job_id: string;
  state: string;
  created_at: string;
};

function DueWork({
  family,
  title,
}: {
  family: 'review' | 'ingest';
  title: string;
}) {
  const query = new URLSearchParams({
    work_type: family,
    due_to: new Date().toISOString().slice(0, 10),
  });
  return (
    <WorkPanel<Task>
      title={title}
      url={`/api/v1/admin/tasks?${query}&offset=0&limit=5`}
      to={`/work?${query}`}
      viewLabel={`View all ${family === 'review' ? 'reviews' : 'ingests'} due`}
      empty={`No pending ${family} Tasks are due.`}
    >
      {(page) => (
        <>
          <p className="text-sm text-text-secondary">
            <strong className="text-xl font-semibold text-text-primary">
              {page.total.toLocaleString()}
            </strong>{' '}
            pending Tasks due
          </p>
          <ul className="divide-y divide-border">
            {page.items.map((item) => (
              <li key={item.task_id} className="py-3 first:pt-0 last:pb-0">
                <Link
                  className="text-sm font-semibold hover:underline [overflow-wrap:anywhere]"
                  to={`/tasks/${encodeURIComponent(item.task_id)}`}
                >
                  {item.title}
                </Link>
                <span className={ui.code}>
                  {item.set_title} · due {item.due_on}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-4 mb-0 text-xs text-text-secondary">
            Showing {page.items.length} of {page.total.toLocaleString()} ·
            ordered by due date
          </p>
        </>
      )}
    </WorkPanel>
  );
}

type ReadState<T> =
  | { status: 'loading' }
  | { status: 'ready'; page: Page<T> }
  | { status: 'error'; error: unknown };

function WorkPanel<T>({
  title,
  url,
  to,
  viewLabel,
  empty,
  children,
}: {
  title: string;
  url: string;
  to: string;
  viewLabel: string;
  empty: string;
  children: (page: Page<T>) => ReactNode;
}) {
  const [state, setState] = useState<ReadState<T>>({ status: 'loading' });
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    request<Page<T>>(url, { signal: controller.signal })
      .then((page) => {
        if (!controller.signal.aborted) setState({ status: 'ready', page });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setState({ status: 'error', error });
      });
    return () => controller.abort();
  }, [url, revision]);

  const accessError =
    state.status === 'error' &&
    state.error instanceof ApiError &&
    ['unauthenticated', 'forbidden'].includes(state.error.code);

  return (
    <section className={`${ui.panel} min-w-0`} aria-label={title}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h3 className="mb-0">{title}</h3>
        <ActionButton
          className={ui.textAction}
          aria-label={`Refresh ${title.toLowerCase()}`}
          disabled={state.status === 'loading'}
          onClick={() => {
            setState({ status: 'loading' });
            setRevision((value) => value + 1);
          }}
        >
          Refresh
        </ActionButton>
      </div>
      <div aria-live="polite" aria-busy={state.status === 'loading'}>
        {state.status === 'loading' && (
          <p className="text-sm text-text-secondary" role="status">
            Loading {title.toLowerCase()}…
          </p>
        )}
        {state.status === 'error' && (
          <div className="text-sm text-text-secondary">
            <p>
              {accessError
                ? 'Sign-in or additional access is needed to view this work.'
                : `${title} could not be loaded. Refresh to try again.`}
            </p>
            {accessError && (
              <Link className="font-medium hover:underline" to="/access">
                Check access
              </Link>
            )}
          </div>
        )}
        {state.status === 'ready' &&
          (state.page.total === 0 ? (
            <p className="text-sm text-text-secondary">{empty}</p>
          ) : (
            children(state.page)
          ))}
      </div>
      <div className="mt-4 border-t border-border pt-3">
        <Link
          className="inline-flex min-h-8 items-center text-sm font-medium hover:underline"
          to={to}
        >
          {viewLabel}{' '}
          <span className="ml-2" aria-hidden="true">
            →
          </span>
        </Link>
      </div>
    </section>
  );
}
