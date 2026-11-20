import { appUrl } from '../api';
import { resourcePath, encodeId } from '../urlIds';
import { CompactActivity } from '../ui/CompactActivity';
import { ui } from '../ui/styles';
import { TextInput, ActionButton, DataTable } from '../ui/controls';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router';
import {
  request,
  sourceBase,
  sourceResources,
  type Source,
  type SourceContract,
  type Page,
} from './api';

export function Load<T>({
  url,
  children,
}: {
  url: string;
  children: (data: T) => ReactNode;
}) {
  const [retry, setRetry] = useState(0);
  return (
    <Read<T>
      key={`${url}:${retry}`}
      url={url}
      retry={() => setRetry(retry + 1)}
    >
      {children}
    </Read>
  );
}
function Read<T>({
  url,
  retry,
  children,
}: {
  url: string;
  retry: () => void;
  children: (data: T) => ReactNode;
}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const alert = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    request<T>(url)
      .then((value) => {
        if (active) setData(value);
      })
      .catch((failure: Error) => {
        if (active) setError(failure);
      });
    return () => {
      active = false;
    };
  }, [url]);
  useEffect(() => {
    if (error) alert.current?.focus();
  }, [error]);
  if (error)
    return (
      <div role="alert" tabIndex={-1} ref={alert} className={ui.error}>
        <p>{error.message}</p>
        <ActionButton type="button" className={ui.secondary} onClick={retry}>
          Try again
        </ActionButton>
      </div>
    );
  if (!data) return <p role="status">Loading…</p>;
  return children(data);
}
export function Pages({
  page,
  change,
  label,
}: {
  page: Page<unknown>;
  change: (offset: number) => void;
  label: string;
}) {
  return (
    <nav className={ui.pagination} aria-label={label}>
      <ActionButton
        type="button"
        className={ui.secondary}
        disabled={page.offset === 0}
        onClick={() => change(Math.max(0, page.offset - page.limit))}
      >
        Previous
      </ActionButton>
      <span role="status">
        {page.total
          ? `${page.offset + 1}–${page.offset + page.items.length} of ${page.total}`
          : '0 results'}
      </span>
      <ActionButton
        type="button"
        className={ui.secondary}
        disabled={page.offset + page.limit >= page.total}
        onClick={() => change(page.offset + page.limit)}
      >
        Next
      </ActionButton>
    </nav>
  );
}
export function SourceList() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  return (
    <main id="main-content" className={ui.page}>
      <h1>Sources</h1>
      <p className={ui.intro}>Independent groupings of Resources.</p>
      <Load<SourceContract> url={'/api/v1/admin/contracts/sources'}>
        {(contract) => (
          <>
            {contract.create && (
              <Link className={ui.primary} to={`/sources/new?${params}`}>
                Create Source
              </Link>
            )}
            {(contract.create || contract.update) && (
              <Link className={ui.secondary} to="/sources/csv/import">
                Import CSV
              </Link>
            )}
            <a
              className={ui.secondary}
              href={appUrl('/api/v1/admin/sources/csv/export')}
            >
              Export for editing
            </a>
            <form
              className={ui.search}
              role="search"
              onSubmit={(event) => {
                event.preventDefault();
                setParams({
                  q: String(
                    new FormData(event.currentTarget).get('q') ?? ''
                  ).trim(),
                });
              }}
            >
              <label htmlFor="source-search">
                Search Sources by title, ID, or legacy code
              </label>
              <div className={ui.inline}>
                <TextInput
                  key={q}
                  defaultValue={q}
                  type="search"
                  name="q"
                  id="source-search"
                  maxLength={200}
                />
                <ActionButton className={ui.secondary}>Search</ActionButton>
              </div>
            </form>
            <Load<Page<Source>>
              url={`${sourceBase}?${new URLSearchParams({ q, offset: String(offset), limit: '25' })}`}
            >
              {(page) => (
                <>
                  {page.items.length ? (
                    <div
                      className={ui.tableRegion}
                      role="region"
                      aria-label="Source results"
                      tabIndex={0}
                    >
                      <DataTable>
                        <thead>
                          <tr>
                            <th scope="col">Title / Source ID</th>
                            <th scope="col">Legacy code</th>
                            <th scope="col">Updated</th>
                          </tr>
                        </thead>
                        <tbody>
                          {page.items.map((item) => (
                            <tr key={item.source_id}>
                              <th scope="row">
                                <Link
                                  to={`/sources/${encodeId(item.source_id)}?${params}`}
                                >
                                  {item.title}
                                </Link>
                                <small className={ui.code}>
                                  {item.source_id}
                                </small>
                              </th>
                              <td>{item.legacy_code || '—'}</td>
                              <td>
                                <time dateTime={item.updated_at}>
                                  {new Date(
                                    item.updated_at
                                  ).toLocaleDateString()}
                                </time>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    </div>
                  ) : (
                    <p>No Sources found. Try a different search.</p>
                  )}
                  <Pages
                    page={page}
                    label="Source pages"
                    change={(next) => setParams({ q, offset: String(next) })}
                  />
                </>
              )}
            </Load>
          </>
        )}
      </Load>
    </main>
  );
}
export function SourceHistory({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  type Entry = {
    id: string;
    action: string;
    outcome: string;
    actor_display_name: string;
    occurred_at: string;
    reason: string | null;
    details: { fields?: string[] };
  };
  return (
    <section
      className="rounded-lg border border-border bg-surface p-4 shadow-xs"
      aria-labelledby="source-history"
    >
      <h2 id="source-history">Source history</h2>
      <Load<Page<Entry>>
        url={`${sourceBase}/${encodeURIComponent(id)}/activity?offset=${offset}&limit=20`}
      >
        {(page) => (
          <>
            {page.items.length ? (
              <CompactActivity entries={page.items} />
            ) : (
              <p>No Source history.</p>
            )}
            <Pages
              label="Source history pages"
              page={page}
              change={setOffset}
            />
          </>
        )}
      </Load>
    </section>
  );
}
export function SourceResources({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const [q, setQ] = useState('');
  type Resource = {
    id: string;
    set_id?: string;
    set_title?: string;
    publication_state?: string;
    metadata: { dct_title_s?: string; gbl_resourceClass_sm?: string[] };
  };
  const query = sourceResources(id);
  if (q) query.set('q', q);
  return (
    <section aria-labelledby="source-resources">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="source-resources">Associated Resources</h2>
          <p className="text-sm text-text-secondary">
            Only Resources within your access are shown.
          </p>
        </div>
        <Link className={ui.secondary} to={`/resources?${query}`}>
          Browse associated Resources
        </Link>
      </div>
      <form
        role="search"
        aria-label="Associated Resources"
        className={ui.search}
        onSubmit={(event) => {
          event.preventDefault();
          setQ(String(new FormData(event.currentTarget).get('q') ?? '').trim());
          setOffset(0);
        }}
      >
        <label htmlFor="associated-resource-search">
          Search within this Source
        </label>
        <div className={ui.inline}>
          <TextInput
            key={q}
            className="basis-full sm:basis-auto"
            id="associated-resource-search"
            name="q"
            type="search"
            maxLength={200}
            defaultValue={q}
          />
          <ActionButton>Search Resources</ActionButton>
          {q && (
            <ActionButton
              type="button"
              onClick={() => {
                setQ('');
                setOffset(0);
              }}
            >
              Clear search
            </ActionButton>
          )}
        </div>
      </form>
      <Load<Page<Resource>>
        url={`/api/v1/admin/resources?${query}&offset=${offset}&limit=20`}
      >
        {(page) => (
          <>
            <p className="text-sm font-semibold">
              {page.total.toLocaleString()} {q ? 'matching' : 'associated'}{' '}
              {page.total === 1 ? 'Resource' : 'Resources'}
            </p>
            {page.items.length ? (
              <div
                className={ui.tableRegion}
                role="region"
                aria-label="Associated Resource results"
                tabIndex={0}
              >
                <DataTable>
                  <thead>
                    <tr>
                      <th scope="col">Resource / ID</th>
                      <th scope="col">Class</th>
                      <th scope="col">Set</th>
                      <th scope="col">Publication</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((item) => (
                      <tr key={item.id}>
                        <th scope="row">
                          <Link to={`${resourcePath(item.id)}?${query}`}>
                            {item.metadata.dct_title_s || item.id}
                          </Link>
                          <small className={ui.code}>{item.id}</small>
                        </th>
                        <td>
                          {Array.isArray(item.metadata.gbl_resourceClass_sm)
                            ? item.metadata.gbl_resourceClass_sm.join(', ') ||
                              '—'
                            : '—'}
                        </td>
                        <td>
                          {item.set_id ? (
                            <Link
                              to={`/sets/${encodeURIComponent(item.set_id)}`}
                            >
                              {item.set_title || item.set_id}
                            </Link>
                          ) : (
                            item.set_title || '—'
                          )}
                        </td>
                        <td>
                          {item.publication_state ? (
                            <span className={ui.badge}>
                              {item.publication_state}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </DataTable>
              </div>
            ) : (
              <p>
                {q
                  ? 'No Resources match this search. Try another term or clear the search.'
                  : 'No associated Resources within your access.'}
              </p>
            )}
            <Pages
              label="Associated Resource pages"
              page={page}
              change={setOffset}
            />
          </>
        )}
      </Load>
    </section>
  );
}
