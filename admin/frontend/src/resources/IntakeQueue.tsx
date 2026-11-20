import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router';
import { resourcePath } from '../urlIds';
import { ApiError, request } from '../api';
import { loadImportSets, type SetRecord } from '../sets/api';
import {
  ActionButton,
  DataTable,
  SelectControl,
  TextArea,
  TextInput,
} from '../ui/controls';
import { ui } from '../ui/styles';
import { CsvReportDownload, type Preview } from './ResourceCsv';

const path = '/resources/csv/intake';
const api = '/api/v1/admin' + path;
const limit = 50;
type Batch = {
  id: string;
  created_at: string;
  uploader: string;
  pending: number;
};
type Draft = {
  catalog_id?: string | null;
  row_number: number;
  resource_id: string;
  title: string;
  csv: string;
  version: number;
};
type DraftPage = { pending: number; items: Draft[] };
const message = (err: unknown) =>
  err instanceof Error ? err.message : 'Request failed. Try again.';
function mutation(body: unknown, key?: string, method = 'POST'): RequestInit {
  return {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-GEOMG-Request': '1',
      ...(key ? { 'Idempotency-Key': key } : {}),
    },
    body: JSON.stringify(body),
  };
}

export function IntakeQueue() {
  const { batchId } = useParams();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [batchId]);
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={batchId ? path : '/resources'}>
        ← {batchId ? 'All uploads' : 'Resources'}
      </Link>
      <h1 tabIndex={-1} ref={heading}>
        {batchId ? 'Imported Resources' : 'Unassigned drafts'}
      </h1>
      {batchId ? <Upload key={batchId} id={batchId} /> : <Uploads />}
    </main>
  );
}

function Uploads() {
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<Batch[]>();
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    request<Batch[]>(api + '?limit=' + limit + '&offset=' + offset, {
      signal: controller.signal,
    })
      .then((rows) => {
        if (!controller.signal.aborted) setItems(rows);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(message(err));
      });
    return () => controller.abort();
  }, [offset]);
  return (
    <>
      <Link className={ui.primary} to="/resources/csv">
        Import Resource CSV
      </Link>
      {error && <p role="alert">{error}</p>}
      {items && (
        <>
          <h2>Uploads</h2>
          {items.length === 0 ? (
            <p>No uploads on this page.</p>
          ) : (
            <div className={ui.tableRegion}>
              <DataTable>
                <thead>
                  <tr>
                    <th>Upload</th>
                    <th>Uploaded by</th>
                    <th>Pending drafts</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((batch) => (
                    <tr key={batch.id}>
                      <th scope="row">
                        <Link to={path + '/' + batch.id}>
                          {new Date(batch.created_at).toLocaleString()}
                        </Link>
                      </th>
                      <td>{batch.uploader}</td>
                      <td>{batch.pending}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </div>
          )}
          <nav className={ui.pagination} aria-label="Upload pages">
            <ActionButton
              disabled={!offset}
              onClick={() => setOffset(offset - limit)}
            >
              Previous uploads
            </ActionButton>
            <ActionButton
              disabled={items.length < limit}
              onClick={() => setOffset(offset + limit)}
            >
              Next uploads
            </ActionButton>
          </nav>
        </>
      )}
    </>
  );
}

function Outcomes({ report }: { report: Preview }) {
  const [page, setPage] = useState(0);
  return (
    <>
      <div className={ui.tableRegion}>
        <DataTable>
          <thead>
            <tr>
              <th>CSV row</th>
              <th>Resource ID</th>
              <th>Outcome</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {report.items.slice(page * limit, (page + 1) * limit).map((r) => (
              <tr key={r.row}>
                <td>{r.row}</td>
                <th scope="row">
                  {r.resource_id &&
                  ['assigned', 'created'].includes(r.outcome) ? (
                    <Link to={resourcePath(r.resource_id)}>
                      {r.resource_id}
                    </Link>
                  ) : (
                    r.resource_id
                  )}
                </th>
                <td>{r.outcome}</td>
                <td>{[...r.errors, ...r.warnings].join(' ')}</td>
              </tr>
            ))}
          </tbody>
        </DataTable>
      </div>
      {report.items.length > limit && (
        <nav className={ui.pagination}>
          <ActionButton disabled={!page} onClick={() => setPage(page - 1)}>
            Previous outcomes
          </ActionButton>
          <ActionButton
            disabled={(page + 1) * limit >= report.items.length}
            onClick={() => setPage(page + 1)}
          >
            Next outcomes
          </ActionButton>
        </nav>
      )}
    </>
  );
}

function Upload({ id }: { id: string }) {
  const base = api + '/' + id;
  const saved = useLocation().state?.saved;
  const [page, setPage] = useState<DraftPage>();
  const [offset, setOffset] = useState(0);
  const [revision, refresh] = useState(0);
  const [sets, setSets] = useState<SetRecord[]>([]);
  const [setId, setSetId] = useState('');
  const [selected, select] = useState<number[]>([]);
  const [all, setAll] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [preview, setPreview] = useState<Preview>();
  const [result, setResult] = useState<Preview>();
  const [receipt, setReceipt] = useState<Preview>();
  const [editing, edit] = useState<Draft>();
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    if (!assigning) return;
    loadImportSets(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setSets(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(message(err));
      });
    return () => controller.abort();
  }, [assigning]);
  useEffect(() => {
    const controller = new AbortController();
    request<DraftPage>(base + '?offset=' + offset + '&limit=' + limit, {
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) return;
        if (!data.items.length && data.pending && offset >= data.pending) {
          setOffset(Math.floor((data.pending - 1) / limit) * limit);
        } else {
          setPage(data);
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(message(err));
      });
    return () => controller.abort();
  }, [base, offset, revision]);
  function resetPlan() {
    setPreview(undefined);
    setResult(undefined);
    setError('');
  }
  function reload() {
    select([]);
    setAll(false);
    setOffset(0);
    setPage(undefined);
    refresh((v) => v + 1);
  }
  async function run(action: 'preview' | 'confirm' | 'edit' | 'receipt') {
    setBusy(true);
    setError('');
    try {
      const body = { set_id: setId, rows: all ? null : selected };
      if (action === 'preview') {
        setPreview(
          await request<Preview>(base + '/assignments/preview', mutation(body))
        );
        setKey(crypto.randomUUID());
        setResult(undefined);
      } else if (action === 'confirm' && preview) {
        const saved = await request<Preview>(
          base + '/assignments',
          mutation(
            { ...body, confirmed: true, preview_hash: preview.preview_hash },
            key
          )
        );
        setResult(saved);
        setPreview(undefined);
        reload();
      } else if (action === 'edit' && editing) {
        await request<Draft>(
          base + '/rows/' + editing.row_number,
          mutation({ csv: editing.csv, version: editing.version }, key, 'PATCH')
        );
        edit(undefined);
        resetPlan();
        reload();
      } else if (action === 'receipt') {
        setReceipt(await request<Preview>(base + '/receipt'));
      }
    } catch (err) {
      setError(message(err));
      if (
        err instanceof ApiError &&
        ['stale_preview', 'stale_version'].includes(err.code)
      ) {
        setPreview(undefined);
        edit(undefined);
        reload();
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {typeof saved === 'number' && (
        <p className={ui.notice} role="status">
          <strong>Upload saved.</strong> {saved}{' '}
          {saved === 1 ? 'row was' : 'rows were'} saved in Resources. Open a
          title to view its metadata.
        </p>
      )}
      <div className={ui.toolbar}>
        <p role="status">
          {page
            ? `${page.pending} unassigned draft${page.pending === 1 ? '' : 's'} in this upload`
            : 'Loading drafts…'}
        </p>
        <ActionButton
          disabled={busy}
          onClick={() =>
            receipt ? setReceipt(undefined) : void run('receipt')
          }
        >
          {receipt ? 'Hide' : 'View'} upload receipt
        </ActionButton>
      </div>
      <Link className={ui.secondary} to="/resources">
        Browse Resources
      </Link>
      {receipt && (
        <section>
          <h2>Original upload receipt</h2>
          <CsvReportDownload report={receipt} />
          <Outcomes report={receipt} />
        </section>
      )}
      {error && (
        <p className={ui.error} role="alert">
          {error}
        </p>
      )}
      {result && (
        <section>
          <h2>Assignment results</h2>
          <p role="status">
            {
              result.items.filter(
                (r) => r.outcome === 'created' || r.outcome === 'assigned'
              ).length
            }{' '}
            drafts assigned.
          </p>
          <Outcomes report={result} />
        </section>
      )}
      {page && page.pending > 0 && (
        <fieldset disabled={busy} className={ui.panel}>
          <legend>Drafts in this upload</legend>
          <ActionButton
            aria-expanded={assigning}
            onClick={() => {
              setAssigning(!assigning);
              resetPlan();
              select([]);
              setAll(false);
            }}
          >
            {' '}
            {assigning ? 'Cancel assignment' : 'Assign to a Set…'}
          </ActionButton>
          {assigning && (
            <label className={ui.checkbox}>
              <TextInput
                type="checkbox"
                checked={all}
                disabled={!!editing}
                onChange={(e) => {
                  resetPlan();
                  setAll(e.target.checked);
                  select([]);
                }}
              />
              Select all {page.pending} pending{' '}
              {page.pending === 1 ? 'draft' : 'drafts'} in this upload
            </label>
          )}
          <div className={ui.tableRegion}>
            <DataTable>
              <thead>
                <tr>
                  {assigning && <th>Select</th>}
                  <th>Row</th>
                  <th>Title and Resource ID</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((d) => (
                  <tr key={d.row_number}>
                    {assigning && (
                      <td>
                        <TextInput
                          type="checkbox"
                          aria-label={'Select ' + d.resource_id}
                          checked={all || selected.includes(d.row_number)}
                          disabled={all || !!editing}
                          onChange={(e) => {
                            resetPlan();
                            select(
                              e.target.checked
                                ? [...selected, d.row_number]
                                : selected.filter((x) => x !== d.row_number)
                            );
                          }}
                        />
                      </td>
                    )}
                    <td>{d.row_number}</td>
                    <th scope="row">
                      {d.catalog_id ? (
                        <Link to={resourcePath(d.catalog_id)}>{d.title}</Link>
                      ) : (
                        d.title
                      )}
                      <span className={ui.code}>{d.resource_id}</span>
                    </th>
                    <td>
                      {d.catalog_id ? (
                        <Link
                          className={ui.secondary}
                          to={resourcePath(d.catalog_id)}
                        >
                          View Resource
                        </Link>
                      ) : (
                        <ActionButton
                          disabled={!!editing}
                          onClick={() => {
                            resetPlan();
                            edit(d);
                            setKey(crypto.randomUUID());
                          }}
                        >
                          Edit row {d.row_number}
                        </ActionButton>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          {page.pending > limit && (
            <nav className={ui.pagination}>
              <ActionButton
                disabled={!offset || !!editing}
                onClick={() => {
                  setPage(undefined);
                  setOffset(offset - limit);
                }}
              >
                Previous drafts
              </ActionButton>
              <ActionButton
                disabled={offset + limit >= page.pending || !!editing}
                onClick={() => {
                  setPage(undefined);
                  setOffset(offset + limit);
                }}
              >
                Next drafts
              </ActionButton>
            </nav>
          )}
          {editing ? (
            <div className={ui.form}>
              <label className={ui.field}>
                Draft CSV for row {editing.row_number}
                <TextArea
                  value={editing.csv}
                  onChange={(e) => {
                    edit({ ...editing, csv: e.target.value });
                    setKey(crypto.randomUUID());
                  }}
                />
              </label>
              <div className={ui.actions}>
                <ActionButton onClick={() => void run('edit')}>
                  Save draft edits
                </ActionButton>
                <ActionButton onClick={() => edit(undefined)}>
                  Cancel edit
                </ActionButton>
              </div>
            </div>
          ) : (
            assigning && (
              <>
                <label className={ui.field}>
                  Optional destination Set
                  <SelectControl
                    value={setId}
                    onChange={(e) => {
                      resetPlan();
                      setSetId(e.target.value);
                    }}
                  >
                    <option value="">Choose a Set</option>
                    {sets.map((s) => (
                      <option key={s.set_id} value={s.set_id}>
                        {s.title} ({s.set_id})
                      </option>
                    ))}
                  </SelectControl>
                </label>
                <ActionButton
                  disabled={!setId || (!all && !selected.length)}
                  onClick={() => void run('preview')}
                >
                  Preview assignment
                </ActionButton>
                {preview && (
                  <section>
                    <h2>Assignment preview</h2>
                    <p>
                      {preview.ready} ready for{' '}
                      {sets.find((s) => s.set_id === setId)?.title}. Skipped and
                      invalid rows stay in the queue.
                    </p>
                    <Outcomes key={preview.preview_hash} report={preview} />
                    <ActionButton
                      className={ui.primary}
                      disabled={!preview.ready}
                      onClick={() => void run('confirm')}
                    >
                      Assign {preview.ready}{' '}
                      {preview.ready === 1 ? 'draft' : 'drafts'} to Set
                    </ActionButton>
                  </section>
                )}
              </>
            )
          )}
        </fieldset>
      )}
    </>
  );
}
