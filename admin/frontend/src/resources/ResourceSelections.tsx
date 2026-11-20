import { showWorkManagement } from '../config/features';
import { resourcePath } from '../urlIds';
import { ui } from '../ui/styles';
import { ActionButton, DataTable } from '../ui/controls';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { request } from '../sets/api';

const base = '/api/v1/admin/resources/selections';
export function SaveSelection({
  q,
  setId,
  filters,
  total,
  bulk = false,
  selected = [],
}: {
  q: string;
  setId: string;
  filters: string;
  total: number;
  bulk?: boolean;
  selected?: string[];
}) {
  const navigate = useNavigate();
  const retry = useRef<{ body: string; key: string } | null>(null);
  const [saved, setSaved] = useState<{
    selection_id: string;
    total: number;
  } | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function snapshot(action: 'save' | 'edit-all' | 'edit-selected') {
    if (action === 'edit-selected' && !selected.length) return;
    setBusy(true);
    setError('');
    try {
      const body = JSON.stringify({
        q,
        set_id: setId || null,
        filters: filters ? JSON.parse(filters) : {},
        ...(action === 'edit-selected' && { ids: [...selected].sort() }),
      });
      if (retry.current?.body !== body)
        retry.current = { body, key: crypto.randomUUID() };
      const selection = await request<{ selection_id: string; total: number }>(
        base,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-GEOMG-Request': '1',
            'Idempotency-Key': retry.current.key,
          },
          body,
        }
      );
      retry.current = null;
      if (action === 'save') setSaved(selection);
      else
        navigate(`/resources/selections/${selection.selection_id}/bulk-edit`);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="mb-4 flex flex-wrap items-center gap-2"
      aria-label="Select matching Resources"
    >
      {bulk && (
        <ActionButton
          className={selected.length ? ui.secondary : ui.primary}
          disabled={busy}
          onClick={() => void snapshot('edit-all')}
        >
          Edit all {total.toLocaleString()} {total === 1 ? 'match' : 'matches'}
        </ActionButton>
      )}
      {bulk && selected.length > 0 && (
        <ActionButton
          className={ui.primary}
          disabled={busy}
          onClick={() => void snapshot('edit-selected')}
        >
          Edit {selected.length.toLocaleString()} selected
        </ActionButton>
      )}
      {saved ? (
        <p role="status">
          {saved.total} Resource versions selected.{' '}
          <Link to={`/resources/selections/${saved.selection_id}`}>
            Review saved selection
          </Link>
        </p>
      ) : (
        <ActionButton
          className={ui.secondary}
          disabled={busy}
          onClick={() => void snapshot('save')}
        >
          {busy
            ? 'Saving selection…'
            : `Select all ${total} matching Resources`}
        </ActionButton>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}

type Page = {
  can_bulk_edit?: boolean;
  validation_set_id?: string | null;
  items: {
    resource_id: string;
    set_id: string | null;
    resource_version: number;
    current_version: number;
  }[];
  total: number;
};
export function ResourceSelectionPage() {
  const { selectionId } = useParams();
  return <Selection key={selectionId} id={selectionId!} />;
}
function Selection({ id }: { id: string }) {
  const navigate = useNavigate();
  const jobKey = useRef<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [jobError, setJobError] = useState('');
  async function validate(setId: string) {
    jobKey.current ??= crypto.randomUUID();
    setSubmitting(true);
    setJobError('');
    try {
      const job = await request<{ job_id: string }>('/api/v1/admin/jobs', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-GEOMG-Request': '1',
          'Idempotency-Key': jobKey.current,
        },
        body: JSON.stringify({ set_id: setId, selection_id: id }),
      });
      navigate(`/jobs/${job.job_id}`);
    } catch (failure) {
      setJobError((failure as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    request<Page>(`${base}/${id}?offset=${offset}&limit=100`)
      .then((value) => {
        if (active) {
          setPage(value);
          setError(false);
        }
      })
      .catch(() => {
        if (active) {
          setPage(null);
          setError(true);
        }
      });
    return () => {
      active = false;
    };
  }, [id, offset, retry]);
  return (
    <main id="main-content" className={ui.page}>
      <h1>Saved Resource selection</h1>
      <Link className={ui.backLink} to="/resources">
        Back to Resources
      </Link>
      <p className={ui.intro}>
        This selection keeps the saved Resource versions from the matching
        results. Changes made afterward are shown below.
      </p>
      <ActionButton
        onClick={() => {
          setPage(null);
          setRetry((v) => v + 1);
        }}
      >
        Refresh selection
      </ActionButton>
      {error ? (
        <p className={ui.error} role="alert">
          Selection unavailable. Check your current access and retry.
        </p>
      ) : (
        !page && <p role="status">Loading selection…</p>
      )}
      {page && (
        <>
          <p className="mt-5 text-sm text-text-secondary" role="status">
            {page.total} selected Resources
          </p>
          {page.can_bulk_edit && page.total > 0 && (
            <Link
              className={ui.primary}
              to={`/resources/selections/${id}/bulk-edit`}
            >
              Bulk actions
            </Link>
          )}
          {showWorkManagement && page.validation_set_id && (
            <ActionButton
              disabled={submitting}
              onClick={() => void validate(page.validation_set_id!)}
            >
              {submitting
                ? 'Submitting validation…'
                : 'Validate saved selection'}
            </ActionButton>
          )}
          {jobError && (
            <p role="alert">{jobError} Retry uses the same submission key.</p>
          )}
          <div
            className={ui.tableRegion}
            role="region"
            aria-label="Selected Resources"
            tabIndex={0}
          >
            <DataTable>
              <caption className="px-4 py-3 text-left font-semibold">
                Saved and current Resource versions
              </caption>
              <thead>
                <tr>
                  <th scope="col">Resource</th>
                  <th scope="col">Selected version</th>
                  <th scope="col">Current version</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((item) => (
                  <tr key={item.resource_id}>
                    <th scope="row">
                      <Link to={`${resourcePath(item.resource_id)}`}>
                        {item.resource_id}
                      </Link>
                    </th>
                    <td>{item.resource_version}</td>
                    <td>{item.current_version}</td>
                    <td>
                      {item.current_version === item.resource_version
                        ? 'Unchanged'
                        : 'Changed since selection'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          <nav className={ui.pagination} aria-label="Selection pages">
            <ActionButton
              disabled={offset === 0}
              onClick={() => {
                setPage(null);
                setOffset(offset - 100);
              }}
            >
              Previous selection page
            </ActionButton>
            <ActionButton
              disabled={offset + 100 >= page.total}
              onClick={() => {
                setPage(null);
                setOffset(offset + 100);
              }}
            >
              Next selection page
            </ActionButton>
          </nav>
        </>
      )}
    </main>
  );
}
