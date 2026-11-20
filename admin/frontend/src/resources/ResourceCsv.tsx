import { appUrl } from '../api';
import { resourcePath } from '../urlIds';
import { ApiError } from '../api';
import { ui } from '../ui/styles';
import {
  TextInput,
  TextArea,
  SelectControl,
  ActionButton,
  DataTable,
} from '../ui/controls';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { request, loadImportSets, type SetRecord } from '../sets/api';

type Row = {
  row: number;
  resource_id?: string;
  record_id?: string;
  set_id?: string;
  input_rows?: number[];
  link_changes?: {
    added: number;
    removed: number;
    relabeled: number;
    reordered: boolean;
  };
  outcome: string;
  errors: string[];
  warnings: string[];
  clear_fields: string[];
  changes: Record<string, { before: unknown; after: unknown }>;
};
export type Preview = {
  batch_id?: string;
  preview_hash: string;
  ready: number;
  items: Row[];
};

type Entity = 'resources' | 'distributions' | 'sources' | 'sets';
const initialModes = {
  resources: 'upsert',
  distributions: 'add_links',
  sources: 'update',
  sets: 'update',
};
const labels = {
  resources: 'Resources',
  distributions: 'Distributions',
  sources: 'Sources',
  sets: 'Sets',
};

export function CsvReportDownload({ report: displayed }: { report: Preview }) {
  const report = useMemo(
    () =>
      displayed
        ? [
            'rows,id,set_id,outcome,errors,warnings,explicit_clears,changes',
            ...displayed.items.map((row) =>
              [
                row.input_rows?.length ? row.input_rows.join(' | ') : row.row,
                row.resource_id ?? row.record_id,
                row.set_id ?? '',
                row.outcome,
                row.errors.join('; '),
                row.warnings.join('; '),
                row.clear_fields.join('; '),
                JSON.stringify(row.changes),
              ]
                .map((value) => {
                  const text = String(value);
                  const safe = /^[=+@\-\t\r\n']/.test(text) ? "'" + text : text;
                  return '"' + safe.replaceAll('"', '""') + '"';
                })
                .join(',')
            ),
          ].join('\r\n')
        : '',
    [displayed]
  );
  const reportLink = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob([report], { type: 'text/csv;charset=utf-8' })
    );
    if (reportLink.current) reportLink.current.href = url;
    return () => URL.revokeObjectURL(url);
  }, [report]);
  return (
    <a className={ui.secondary} download="csv-outcomes.csv" ref={reportLink}>
      Download row report
    </a>
  );
}

export function ResourceCsv({ entity = 'resources' }: { entity?: Entity }) {
  const links = entity === 'distributions';
  const resourceScope = links || entity === 'resources';
  const base =
    '/api/v1/admin/' + (resourceScope ? 'resources' : entity) + '/csv';
  const downloads = links ? base + '/distributions' : base;
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [managingSet, setSet] = useState(params.get('set_id') ?? '');
  const [sets, setSets] = useState<SetRecord[]>([]);
  const [mode, setMode] = useState(initialModes[entity]);
  const [source, setSource] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRead = useRef(0);
  const key = useRef('');
  const [page, setPage] = useState(0);
  const [outcome, setOutcome] = useState('all');
  useEffect(() => {
    if (!resourceScope) return;
    const controller = new AbortController();
    loadImportSets(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted) setSets(items);
      })
      .catch((err) => {
        if (
          !controller.signal.aborted &&
          !(err instanceof ApiError && err.code === 'forbidden')
        )
          setError('Could not load Sets. Reload to retry.');
      });
    return () => controller.abort();
  }, [resourceScope]);
  function reset() {
    fileRead.current++;
    setPage(0);
    setOutcome('all');
    setPreview(null);
    setResult(null);
    setError('');
    key.current = '';
  }
  async function run(commit: boolean) {
    setBusy(true);
    setError('');
    try {
      const data = await request<Preview>(
        `${base}/${commit ? 'import' : 'preview'}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-GEOMG-Request': '1',
            ...(commit ? { 'Idempotency-Key': key.current } : {}),
          },
          body: JSON.stringify({
            ...(resourceScope && managingSet ? { set_id: managingSet } : {}),
            ...(entity === 'resources' ? {} : { mode }),
            csv: source,
            ...(commit
              ? { preview_hash: preview?.preview_hash, confirmed: true }
              : {}),
          }),
        }
      );
      if (
        commit &&
        data.batch_id &&
        data.items.every((row) => row.outcome === 'created')
      ) {
        navigate('/resources/csv/intake/' + data.batch_id, {
          state: { saved: data.ready },
        });
      } else if (commit) {
        setOutcome('all');
        setPage(0);
        setResult(data);
      } else {
        setPreview(data);
        key.current = crypto.randomUUID();
      }
    } catch (err) {
      if (
        err instanceof ApiError &&
        (err.code === 'stale_preview' || err.code === 'invalid_csv')
      )
        reset();
      setError(
        err instanceof Error ? err.message : 'CSV request failed. Retry.'
      );
    } finally {
      setBusy(false);
    }
  }
  const displayed = result ?? preview;
  const heading = useRef<HTMLHeadingElement>(null);
  const alert = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (displayed) heading.current?.focus();
  }, [displayed]);
  useEffect(() => {
    if (error) alert.current?.focus();
  }, [error]);
  const rows = useMemo(
    () =>
      displayed?.items.filter(
        (row) => outcome === 'all' || row.outcome === outcome
      ) ?? [],
    [displayed, outcome]
  );
  const summary = useMemo(() => {
    const outcomes = new Map<string, number>(),
      scopes = new Map<string, number>(),
      notices = new Map<string, number>();
    for (const row of displayed?.items ?? []) {
      outcomes.set(row.outcome, (outcomes.get(row.outcome) ?? 0) + 1);
      if (
        row.set_id &&
        ['create', 'update', 'created', 'updated'].includes(row.outcome)
      )
        scopes.set(row.set_id, (scopes.get(row.set_id) ?? 0) + 1);
      for (const warning of row.warnings)
        notices.set(warning, (notices.get(warning) ?? 0) + 1);
    }
    return { outcomes, scopes, notices };
  }, [displayed]);
  return (
    <main id="main-content" className={ui.page}>
      <Link
        className={ui.backLink}
        to={
          resourceScope
            ? `/resources${managingSet ? `?set_id=${encodeURIComponent(managingSet)}` : ''}`
            : '/' + entity
        }
      >
        ← {resourceScope ? 'Resources' : labels[entity]}
      </Link>
      <h1>{labels[entity]} CSV import</h1>
      <p className={ui.intro}>
        {links
          ? 'Upload one link per row. Add links keeps existing links in order. Replace links uses the complete ordered list in your file for each included Resource.'
          : resourceScope
            ? 'Use the full Resource CSV template or a complete GBL Admin export. New IDs create drafts. Matching IDs update existing drafts you can edit. On updates, an empty cell clears the field. Choose a Set to place new drafts there and limit updates to that Set. Use pipes between repeatable values under GEOMG headings.'
            : 'Use stable IDs to create records. To update records, edit a current export and keep its lock_version column.'}
        {!resourceScope &&
          ' Blank cells preserve stored values. Use a companion __clear column with true to clear a field.'}
      </p>
      <div className="mb-4 flex flex-wrap gap-3">
        <a
          className={ui.secondary}
          href={appUrl(
            downloads +
              '/template' +
              (entity === 'resources' ? '?format=geomg' : '')
          )}
        >
          Download CSV template
        </a>
        {entity === 'resources' && (
          <>
            <a className={ui.secondary} href={appUrl(base + '/crosswalk')}>
              Download column crosswalk
            </a>
            <Link
              className={ui.secondary}
              to={
                '/resources/csv/distributions' +
                (managingSet
                  ? '?set_id=' + encodeURIComponent(managingSet)
                  : '')
              }
            >
              Import Distribution links
            </Link>
          </>
        )}
        {entity !== 'resources' && (
          <a
            className={ui.secondary}
            href={appUrl(
              downloads +
                '/export' +
                (links && managingSet
                  ? '?set_id=' + encodeURIComponent(managingSet)
                  : '')
            )}
          >
            Export for editing
          </a>
        )}
      </div>
      {error && (
        <p className={ui.notice} role="alert" ref={alert} tabIndex={-1}>
          {error}
        </p>
      )}
      <fieldset
        disabled={busy || !!result}
        className="my-6 grid min-w-0 grid-cols-1 items-start gap-5 rounded-lg border border-border bg-surface p-4 shadow-xs sm:p-6 md:grid-cols-2 [&_legend]:px-2 [&_legend]:font-semibold [&_label]:grid [&_label]:min-w-0 [&_label]:gap-2 [&_textarea]:font-mono [&_button]:justify-self-start"
      >
        <legend>CSV source</legend>
        {resourceScope && (
          <label>
            Set
            <SelectControl
              value={managingSet}
              onChange={(e) => {
                reset();
                setSet(e.target.value);
              }}
            >
              <option value="">
                {entity === 'resources'
                  ? 'No Set for new drafts'
                  : 'All accessible Sets'}
              </option>
              {sets
                .filter((item) => item.status !== 'retired')
                .map((item) => (
                  <option key={item.set_id} value={item.set_id}>
                    {item.title}
                  </option>
                ))}
            </SelectControl>
          </label>
        )}
        {entity !== 'resources' && (
          <label>
            Import mode
            <SelectControl
              value={mode}
              onChange={(e) => {
                reset();
                setMode(e.target.value);
              }}
            >
              {links ? (
                <>
                  <option value="add_links">Add links</option>
                  <option value="replace_links">Replace links</option>
                </>
              ) : (
                <>
                  <option value="update">
                    Update existing {resourceScope ? 'drafts' : entity}
                  </option>
                  <option value="create">
                    Create new {resourceScope ? 'drafts' : entity}
                  </option>
                </>
              )}
            </SelectControl>
          </label>
        )}
        <label>
          CSV file
          <TextInput
            type="file"
            accept=".csv,text/csv"
            onChange={async (e) => {
              reset();
              setSource('');
              const read = fileRead.current;
              const file = e.target.files?.[0];
              if (!file) return;
              try {
                const content = await file.text();
                if (read === fileRead.current) setSource(content);
              } catch {
                if (read === fileRead.current)
                  setError('The file could not be read. Choose it again.');
              }
            }}
          />
        </label>
        <label className="col-span-full">
          CSV text
          <TextArea
            rows={7}
            value={source}
            onChange={(e) => {
              reset();
              setSource(e.target.value);
            }}
          />
        </label>
        <ActionButton
          className={ui.secondary}
          disabled={!source}
          onClick={() => void run(false)}
        >
          Preview CSV
        </ActionButton>
      </fieldset>
      {busy && (
        <p role="status">
          Processing CSV… Keep this page open while the server validates and
          saves your file.
        </p>
      )}
      {displayed && (
        <section aria-label="CSV outcomes">
          <h2 ref={heading} tabIndex={-1}>
            {result ? 'Import results' : 'Preview changes'}
          </h2>
          <p role="status">
            {result
              ? `${(summary.outcomes.get('created') ?? 0) + (summary.outcomes.get('updated') ?? 0)} records applied`
              : `${displayed.ready} records ready`}
            .{' '}
            {Array.from(
              summary.outcomes,
              ([name, count]) => `${name} ${count}`
            ).join(' · ')}
          </p>
          {result?.batch_id && (
            <Link
              className={ui.backLink}
              to={'/resources/csv/intake/' + result.batch_id}
            >
              View saved upload
            </Link>
          )}
          {resourceScope && summary.scopes.size > 0 && (
            <details>
              <summary>Totals by managing Set</summary>
              <ul>
                {Array.from(summary.scopes, ([id, count]) => (
                  <li key={id}>
                    {id} · {count}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {!result && (
            <ActionButton
              className={ui.primary}
              disabled={busy || !preview?.ready}
              onClick={() => void run(true)}
            >
              {`Apply ${displayed.ready} ready ${links ? 'Resource group' : 'row'}${displayed.ready === 1 ? '' : 's'}`}
            </ActionButton>
          )}
          {summary.notices.size > 0 && (
            <details>
              <summary>Import notes</summary>
              <ul>
                {Array.from(summary.notices, ([message, count]) => (
                  <li key={message}>
                    {message} ({count})
                  </li>
                ))}
              </ul>
            </details>
          )}
          <CsvReportDownload report={displayed} />
          <label>
            Show outcomes
            <SelectControl
              value={outcome}
              onChange={(event) => {
                setOutcome(event.target.value);
                setPage(0);
              }}
            >
              <option value="all">All rows</option>
              {[...new Set(displayed.items.map((row) => row.outcome))].map(
                (value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                )
              )}
            </SelectControl>
          </label>
          <p>
            {rows.length} matching rows · Page {page + 1} of{' '}
            {Math.max(1, Math.ceil(rows.length / 100))}
          </p>
          <div
            className={ui.tableRegion}
            role="region"
            aria-label="CSV preview"
            tabIndex={0}
          >
            <DataTable>
              <thead>
                <tr>
                  <th>Row / ID</th>
                  <th>Outcome</th>
                  <th>Changes and validation</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(page * 100, (page + 1) * 100).map((row) => (
                  <tr key={row.row}>
                    <th scope="row">
                      {row.input_rows?.length
                        ? row.input_rows.join(', ')
                        : row.row}
                      <span className={ui.code}>
                        {entity === 'resources' &&
                        row.resource_id &&
                        ['update', 'created', 'updated', 'unchanged'].includes(
                          row.outcome
                        ) ? (
                          <Link to={resourcePath(row.resource_id)}>
                            {row.resource_id}
                          </Link>
                        ) : (
                          (row.resource_id ?? row.record_id)
                        )}
                      </span>
                    </th>
                    <td>{row.outcome}</td>
                    <td>
                      {row.errors.map((message, i) => (
                        <p key={i}>{message}</p>
                      ))}
                      {row.warnings.length > 0 && (
                        <details>
                          <summary>Row notes ({row.warnings.length})</summary>
                          {row.warnings.map((message, i) => (
                            <p key={i}>{message}</p>
                          ))}
                        </details>
                      )}
                      {row.clear_fields.length > 0 && (
                        <p>
                          {result && row.outcome === 'updated'
                            ? 'Cleared fields'
                            : 'Fields to clear'}
                          : {row.clear_fields.join(', ')}
                        </p>
                      )}
                      {row.link_changes && (
                        <p>
                          {row.link_changes.added} added ·{' '}
                          {row.link_changes.removed} removed ·{' '}
                          {row.link_changes.relabeled} relabeled
                          {row.link_changes.reordered && ' · Order changed'}
                        </p>
                      )}
                      {Object.keys(row.changes).length > 0 && (
                        <details>
                          <summary>
                            Review changes ({Object.keys(row.changes).length})
                          </summary>
                          {Object.entries(row.changes).map(([name, change]) => (
                            <dl key={name}>
                              <dt className="font-semibold">{name}</dt>
                              <dd>
                                Before{' '}
                                <code className="whitespace-pre-wrap [overflow-wrap:anywhere]">
                                  {JSON.stringify(change.before)}
                                </code>
                              </dd>
                              <dd>
                                After{' '}
                                <code className="whitespace-pre-wrap [overflow-wrap:anywhere]">
                                  {JSON.stringify(change.after)}
                                </code>
                              </dd>
                            </dl>
                          ))}
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          <div className={ui.pagination}>
            <ActionButton
              className={ui.secondary}
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Previous rows
            </ActionButton>
            <ActionButton
              className={ui.secondary}
              disabled={(page + 1) * 100 >= rows.length}
              onClick={() => setPage(page + 1)}
            >
              Next rows
            </ActionButton>
          </div>
          {result && (
            <ActionButton className={ui.secondary} onClick={reset}>
              Start another CSV import
            </ActionButton>
          )}
        </section>
      )}
    </main>
  );
}
