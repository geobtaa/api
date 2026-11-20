import { appUrl } from '../api';
import { resourcePath } from '../urlIds';
import { ui } from '../ui/styles';
import { TextInput, ActionButton, DataTable } from '../ui/controls';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router';
import { request } from '../sets/api';
import type { Resource } from '../resources/ResourcePages';

const base = '/api/v1/admin/jobs';
type Job = {
  job_id: string;
  set_id: string;
  state: string;
  attempt_number: number;
  totals: Record<string, number>;
};
type ItemPage = {
  items: {
    position: number;
    resource_id: string;
    resource_version: number;
    disposition: string;
    details: { errors?: string[]; warnings?: string[]; code?: string };
  }[];
  total: number;
};
const terminal = (job: Job) => !['queued', 'running'].includes(job.state);

export function ValidateSelection({ selection }: { selection: Resource[] }) {
  const key = useRef<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const sameSet = new Set(selection.map((item) => item.set_id)).size === 1;
  async function submit() {
    setBusy(true);
    setError('');
    key.current ??= crypto.randomUUID();
    try {
      const result = await request<Job>(base, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-GEOMG-Request': '1',
          'Idempotency-Key': key.current,
        },
        body: JSON.stringify({
          set_id: selection[0].set_id,
          selection: selection.map((item) => ({
            resource_id: item.id,
            lock_version: item.lock_version,
          })),
        }),
      });
      setJob(result);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={ui.notice} aria-label="Validate selection">
      <p>
        Validate {selection.length} selected saved drafts. Validation does not
        publish Resources.
      </p>
      {!sameSet && <p>Select Resources from one Set to validate together.</p>}
      {job ? (
        <p role="status">
          Validation submitted.{' '}
          <Link to={`/jobs/${job.job_id}`}>View validation job</Link>
        </p>
      ) : (
        <ActionButton
          className={ui.secondary}
          disabled={busy || !sameSet}
          onClick={() => void submit()}
        >
          {busy
            ? 'Submitting…'
            : error
              ? 'Retry validation submission'
              : 'Validate selected drafts'}
        </ActionButton>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

export function JobPage() {
  const { jobId } = useParams();
  return <JobDetail key={jobId} id={jobId!} />;
}
function JobDetail({ id }: { id: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [page, setPage] = useState<ItemPage | null>(null);
  const [access, setAccess] = useState({
    can_cancel: false,
    can_download: false,
  });
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (cancelling) return;
    async function refresh() {
      try {
        const [next, results, rights] = await Promise.all([
          request<Job>(`${base}/${id}`),
          request<ItemPage>(`${base}/${id}/items?offset=${offset}&limit=100`),
          request<typeof access>('/api/v1/admin/contracts/jobs'),
        ]);
        if (!active) return;
        setJob(next);
        setPage(results);
        setAccess(rights);
        setError('');
        if (!terminal(next)) timer = setTimeout(() => void refresh(), 4000);
      } catch {
        if (active) {
          setJob(null);
          setPage(null);
          setError(
            'Job unavailable. Check your access and connection, then retry.'
          );
        }
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id, offset, retry, cancelling]);
  async function cancel() {
    setBusy(true);
    setCancelling(true);
    setError('');
    try {
      setJob(
        await request<Job>(`${base}/${id}/cancel`, {
          method: 'POST',
          headers: { 'X-GEOMG-Request': '1' },
        })
      );
      setConfirmed(false);
      setPage(null);
      setCancelling(false);
    } catch {
      setError(
        'Cancellation could not be confirmed. Refresh status before retrying.'
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main-content" className={ui.page}>
      <h1>Resource validation job</h1>
      <p className={ui.intro}>
        Keep this URL to return after closing your browser. Results describe
        saved drafts, not publication readiness.
      </p>
      <div className="mb-5 flex flex-wrap gap-5">
        <Link className={ui.backLink} to="/resources">
          Back to Resources
        </Link>
        <Link className={ui.backLink} to="/jobs">
          All jobs
        </Link>
      </div>
      {error && (
        <p className={ui.error} role="alert" tabIndex={-1} ref={errorRef}>
          {error}
        </p>
      )}
      <ActionButton
        className={ui.secondary}
        disabled={busy}
        onClick={() => {
          setCancelling(false);
          setRetry((v) => v + 1);
        }}
      >
        Refresh job
      </ActionButton>
      {!job && !error && <p role="status">Loading job…</p>}
      {job && (
        <>
          <p className={ui.notice} role="status">
            {job.state.replaceAll('_', ' ')} · attempt {job.attempt_number} ·{' '}
            {Object.entries(job.totals)
              .map(([name, count]) => `${count} ${name}`)
              .join(' · ')}
          </p>
          {terminal(job) && access.can_download && (
            <a
              className={`${ui.secondary} mb-5`}
              href={appUrl(`${base}/${id}/report`)}
            >
              Download validation report
            </a>
          )}
          {!terminal(job) && access.can_cancel && (
            <form
              className={`${ui.form} flex flex-wrap items-center gap-4`}
              onSubmit={(event) => {
                event.preventDefault();
                if (confirmed) void cancel();
              }}
            >
              <label className={ui.checkbox}>
                <TextInput
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  disabled={busy}
                />
                Stop remaining validation; retain completed results.
              </label>
              <ActionButton
                className={ui.secondary}
                disabled={!confirmed || busy}
              >
                Cancel remaining work
              </ActionButton>
            </form>
          )}
          {page && (
            <>
              <div
                className={ui.tableRegion}
                tabIndex={0}
                role="region"
                aria-label="Validation results"
              >
                <DataTable>
                  <caption className="px-4 py-3 text-left font-semibold">
                    Results for selected saved versions
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Resource</th>
                      <th scope="col">Version</th>
                      <th scope="col">Outcome</th>
                      <th scope="col">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((item) => (
                      <tr key={item.position}>
                        <th scope="row">
                          <Link to={`${resourcePath(item.resource_id)}`}>
                            {item.resource_id}
                          </Link>
                        </th>
                        <td>{item.resource_version}</td>
                        <td>{item.disposition}</td>
                        <td>
                          {[
                            ...(item.details.errors ?? []),
                            ...(item.details.warnings ?? []),
                            ...(item.details.code
                              ? [item.details.code.replaceAll('_', ' ')]
                              : []),
                          ].join('; ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              </div>
              <nav className={ui.pagination} aria-label="Job result pages">
                <ActionButton
                  disabled={offset === 0 || busy}
                  onClick={() => {
                    setPage(null);
                    setOffset(offset - 100);
                  }}
                >
                  Previous results
                </ActionButton>
                <ActionButton
                  disabled={offset + 100 >= page.total || busy}
                  onClick={() => {
                    setPage(null);
                    setOffset(offset + 100);
                  }}
                >
                  Next results
                </ActionButton>
              </nav>
            </>
          )}
        </>
      )}
    </main>
  );
}

export function JobList() {
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [data, setData] = useState<{ items: Job[]; total: number } | null>(
    null
  );
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    request<{ items: Job[]; total: number }>(
      `${base}?offset=${offset}&limit=100`
    )
      .then((result) => {
        if (active) {
          setData(result);
          setError(false);
        }
      })
      .catch(() => {
        if (active) {
          setData(null);
          setError(true);
        }
      });
    return () => {
      active = false;
    };
  }, [offset, retry]);
  return (
    <main id="main-content" className={ui.page}>
      <h1>Jobs</h1>
      <p className={ui.intro}>
        Recover submissions and inspect durable results within your Set access.
      </p>
      <ActionButton
        onClick={() => {
          setData(null);
          setRetry((v) => v + 1);
        }}
      >
        Refresh jobs
      </ActionButton>
      {error ? (
        <p className={ui.error} role="alert">
          Jobs unavailable. Check your access and connection, then refresh.
        </p>
      ) : (
        !data && <p role="status">Loading jobs…</p>
      )}
      {data && (
        <>
          <p className="mt-5 text-sm text-text-secondary" role="status">
            {data.total} jobs
          </p>
          <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
            {data.items.map((job) => (
              <li
                className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm"
                key={job.job_id}
              >
                <Link
                  className="font-medium hover:underline [overflow-wrap:anywhere]"
                  to={`/jobs/${job.job_id}`}
                >
                  Resource validation · {job.job_id}
                </Link>{' '}
                <span className={ui.badge}>
                  {job.state.replaceAll('_', ' ')}
                </span>
              </li>
            ))}
          </ul>
          <nav className={ui.pagination} aria-label="Job pages">
            <ActionButton
              disabled={offset === 0}
              onClick={() => {
                setData(null);
                setOffset(offset - 100);
              }}
            >
              Previous jobs
            </ActionButton>
            <ActionButton
              disabled={offset + 100 >= data.total}
              onClick={() => {
                setData(null);
                setOffset(offset + 100);
              }}
            >
              Next jobs
            </ActionButton>
          </nav>
        </>
      )}
    </main>
  );
}
