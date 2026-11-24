import { appUrl } from '../api';
import { showWorkManagement } from '../config/features';
import { resourcePath, resourceApiPath, decodeId } from '../urlIds';
import { ui } from '../ui/styles';
import { TextInput, ActionButton } from '../ui/controls';
import { useEffect, useState } from 'react';
import { SaveSelection } from './ResourceSelections';
import { ValidateSelection } from '../jobs/Jobs';
import { ResourceThumbnail } from './ResourceThumbnail';
import { ResourceFacets } from './ResourceFacets';
import { ResourcePreview } from './ResourcePreview';
import { ResourceEditor, type ResourceDetailData } from './ResourceEditor';
import { Link, useParams, useSearchParams } from 'react-router';
import { request, type SetRecord } from '../sets/api';

export type Resource = {
  source_id: string | null;
  can_associate?: boolean;
  id: string;
  set_id: string | null;
  set_title: string | null;
  publication_state: string;
  lock_version: number;
  metadata: Record<string, unknown>;
};
type Page = {
  can_create?: boolean;
  can_bulk_edit?: boolean;
  can_validate?: boolean;
  can_select?: boolean;
  items: Resource[];
  total: number;
  offset: number;
  limit: number;
};
export const resourceBase = '/api/v1/admin/resources';
export function ResourceList() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const setId = params.get('set_id') ?? '';
  const filters = params.get('filters') ?? '';
  const [showFilters, setShowFilters] = useState(false);
  const scope: Record<string, string> = {
    ...(setId ? { set_id: setId } : {}),
    ...(filters ? { filters } : {}),
  };
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  return (
    <main id="main-content" className={ui.page}>
      <p className={ui.kicker}>Metadata administration</p>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h1 className="m-0">Resources</h1>
        <div className="flex flex-wrap items-center gap-3 sm:ml-auto">
          <Link
            className={ui.primary}
            to={`/resources/csv${setId ? `?set_id=${encodeURIComponent(setId)}` : ''}`}
          >
            Import CSV
          </Link>
          <a
            className={ui.secondary}
            href={appUrl(
              `${resourceBase}/csv/export?${new URLSearchParams({ ...scope, q, format: 'geomg' })}`
            )}
          >
            Export filtered CSV
          </a>
        </div>
      </div>
      <p className={ui.intro}>Browse and edit saved Resources.</p>
      {setId && (
        <SetScope
          key={setId}
          id={setId}
          clear={() =>
            setParams({ ...(q ? { q } : {}), ...(filters ? { filters } : {}) })
          }
        />
      )}
      <ActionButton
        className={`${ui.secondary} mb-4 md:hidden`}
        aria-expanded={showFilters}
        aria-controls="resource-sidebar"
        onClick={() => setShowFilters(!showFilters)}
      >
        {showFilters ? 'Hide filters' : 'Show filters'}
      </ActionButton>
      <div className="grid grid-cols-1 items-start gap-5 md:grid-cols-[18rem_minmax(0,1fr)] lg:gap-7">
        <aside
          id="resource-sidebar"
          className={`min-w-0 rounded-lg border border-border bg-surface shadow-xs md:block ${showFilters ? 'block' : 'hidden'}`}
          aria-label="Filter Resources"
        >
          <ResourceFacets
            {...{ q, setId, filters }}
            change={(value) =>
              setParams({
                q,
                ...(setId ? { set_id: setId } : {}),
                ...(value ? { filters: value } : {}),
              })
            }
          />
        </aside>
        <section className="min-w-0" aria-label="Resource results">
          <form
            className="mb-3 flex items-center gap-2 rounded-lg border border-border bg-surface p-3 shadow-xs"
            role="search"
            onSubmit={(event) => {
              event.preventDefault();
              setParams({
                ...scope,
                q: String(
                  new FormData(event.currentTarget).get('q') ?? ''
                ).trim(),
              });
            }}
          >
            <label className="sr-only" htmlFor="resource-search">
              Search title or Resource ID
            </label>
            <div className="flex w-full items-center gap-2">
              <TextInput
                className="h-10 min-w-0 flex-1"
                placeholder="Search title or Resource ID"
                id="resource-search"
                name="q"
                type="search"
                defaultValue={q}
                key={q}
                maxLength={200}
              />
              <ActionButton className={ui.secondary}>Search</ActionButton>
            </div>
          </form>
          <ResourceResults
            key={`${setId}:${q}:${offset}:${filters}`}
            q={q}
            filters={filters}
            setId={setId}
            offset={offset}
            changePage={(next) =>
              setParams({ ...scope, q, offset: String(next) })
            }
          />
        </section>
      </div>
    </main>
  );
}
function SetScope({ id, clear }: { id: string; clear: () => void }) {
  const [title, setTitle] = useState(id);
  useEffect(() => {
    let active = true;
    request<SetRecord>(`/api/v1/admin/sets/${encodeURIComponent(id)}`)
      .then((item) => {
        if (active) setTitle(item.title);
      })
      .catch(() => {
        /* Keep the explicit scope visible even without Set read access. */
      });
    return () => {
      active = false;
    };
  }, [id]);
  return (
    <div className={`${ui.notice} ${ui.toolbar}`} aria-label="Set filter">
      <p>
        Set: <Link to={`/sets/${encodeURIComponent(id)}`}>{title}</Link>
      </p>
      <ActionButton type="button" className={ui.secondary} onClick={clear}>
        Clear Set filter
      </ActionButton>
    </div>
  );
}
function ResourceResults({
  q,
  filters,
  setId,
  offset,
  changePage,
}: {
  q: string;
  filters: string;
  setId: string;
  offset: number;
  changePage: (value: number) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    request<Page>(
      `${resourceBase}?${new URLSearchParams({ q, ...(filters ? { filters } : {}), offset: String(offset), ...(setId ? { set_id: setId } : {}) })}`
    )
      .then((result) => {
        if (active) setPage(result);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [q, setId, offset, retry, filters]);
  if (error)
    return (
      <div role="alert" className={ui.notice}>
        <p>Resources could not be loaded. Check your access and connection.</p>
        <ActionButton
          className={ui.secondary}
          onClick={() => {
            setError(false);
            setRetry(retry + 1);
          }}
        >
          Retry
        </ActionButton>
      </div>
    );
  if (!page) return <p role="status">Loading Resources…</p>;
  const browseParams = new URLSearchParams();
  if (setId) browseParams.set('set_id', setId);
  if (q) browseParams.set('q', q);
  if (filters) browseParams.set('filters', filters);
  if (offset) browseParams.set('offset', String(offset));
  return (
    <>
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm [&>section]:mb-0 [&>section_p]:m-0 [&_button]:px-3 [&_button]:py-1.5 [&_button]:text-sm">
        <p role="status" className="m-0 whitespace-nowrap">
          {page.total.toLocaleString()} Resources · {selected.length} selected
          on page
        </p>
        {page.can_create && (
          <Link
            className={ui.primary}
            to={`/resources/new${setId ? `?set_id=${encodeURIComponent(setId)}` : ''}`}
          >
            New Resource
          </Link>
        )}
        {page.can_select && page.total > 0 && (
          <SaveSelection
            q={q}
            setId={setId}
            filters={filters}
            total={page.total}
            bulk={page.can_bulk_edit}
            selected={selected}
          />
        )}
        {page.can_bulk_edit && (
          <Link className={ui.textAction} to="/resource-bulk-actions">
            My bulk actions
          </Link>
        )}
        {selected.length > 0 && (
          <a
            className={ui.secondary}
            href={appUrl(
              `${resourceBase}/csv/export?${new URLSearchParams([['format', 'geomg'], ...selected.map((id) => ['ids', id]), ...(filters ? [['filters', filters]] : []), ...(q ? [['q', q]] : []), ...(setId ? [['set_id', setId]] : [])])}`
            )}
          >
            Export selected CSV
          </a>
        )}
        <div className="ml-auto">
          <ResourcePagination
            page={page}
            offset={offset}
            changePage={changePage}
            position="top"
          />
        </div>
      </div>
      {showWorkManagement && page.can_validate && selected.length > 0 && (
        <ValidateSelection
          key={selected.join('\u0000')}
          selection={page.items.filter((item) => selected.includes(item.id))}
        />
      )}
      {page.items.length === 0 ? (
        <p>No Resources match. Import a JSON collection to get started.</p>
      ) : (
        <section
          className="overflow-hidden rounded-lg border border-border bg-surface shadow-xs"
          aria-label="Resources"
        >
          <div className="flex items-center gap-3 border-b border-border bg-surface-subtle px-4 py-2 text-xs text-text-secondary">
            <label className="flex items-center gap-3">
              <TextInput
                aria-label="Select all Resources on this page"
                type="checkbox"
                checked={
                  page.items.length > 0 && selected.length === page.items.length
                }
                onChange={(event) =>
                  setSelected(
                    event.target.checked
                      ? page.items.map((item) => item.id)
                      : []
                  )
                }
              />
              Select page
            </label>
            <span className="ml-auto">Saved Resources</span>
          </div>
          <ol className="m-0 list-none divide-y divide-border p-0">
            {page.items.map((item, index) => {
              const metadata = item.metadata;
              const values = (value: unknown): string =>
                Array.isArray(value)
                  ? value
                      .filter(
                        (part) =>
                          typeof part === 'string' || typeof part === 'number'
                      )
                      .join(' · ')
                  : typeof value === 'string' || typeof value === 'number'
                    ? String(value)
                    : '';
              const description = values(metadata.dct_description_sm);
              const context = [
                values(metadata.schema_provider_s),
                values(metadata.gbl_resourceClass_sm),
                values(metadata.dct_issued_s) ||
                  values(metadata.gbl_indexYear_im),
              ].filter(Boolean);
              return (
                <li
                  key={item.id}
                  className={`flex items-start gap-3 px-4 py-2 transition-colors hover:bg-surface-subtle ${selected.includes(item.id) ? 'bg-active-soft' : ''}`}
                >
                  <TextInput
                    className="mt-1 shrink-0"
                    aria-label={`Select ${item.id}`}
                    type="checkbox"
                    checked={selected.includes(item.id)}
                    onChange={(event) =>
                      setSelected(
                        event.target.checked
                          ? [...selected, item.id]
                          : selected.filter((id) => id !== item.id)
                      )
                    }
                  />
                  <ResourceThumbnail key={item.id} id={item.id} />
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5 sm:h-24">
                    <div className="flex items-baseline gap-2">
                      <span className="shrink-0 text-xs text-text-muted tabular-nums">
                        {(offset + index + 1).toLocaleString()}.
                      </span>
                      <Link
                        className="min-w-0 text-base font-semibold leading-snug text-active [overflow-wrap:anywhere] hover:underline sm:truncate"
                        title={String(metadata.dct_title_s)}
                        to={`${resourcePath(item.id)}${browseParams.size ? `?${browseParams}` : ''}`}
                      >
                        {String(metadata.dct_title_s)}
                      </Link>
                      <span
                        className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold ${item.publication_state === 'published' ? 'bg-success-soft text-success' : 'bg-surface-muted text-text-secondary'}`}
                      >
                        {item.publication_state}
                      </span>
                    </div>
                    {context.length > 0 && (
                      <p
                        className="m-0 truncate text-xs leading-4 text-text-secondary"
                        title={context.join(' · ')}
                      >
                        {context.join(' · ')}
                      </p>
                    )}
                    {description && (
                      <p className="m-0 line-clamp-2 text-sm leading-[18px] text-text-secondary">
                        {description}
                      </p>
                    )}
                    <div className="mt-auto flex min-w-0 items-center gap-3 text-xs leading-4 text-text-muted">
                      <span
                        className="min-w-0 truncate font-mono"
                        title={item.id}
                      >
                        {item.id}
                      </span>
                      {item.set_id && (
                        <Link
                          className="min-w-0 truncate text-primary hover:underline"
                          title={item.set_title ?? undefined}
                          to={`/sets/${item.set_id}`}
                        >
                          {item.set_title}
                        </Link>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      )}
      <div className="mt-3 flex justify-end">
        <ResourcePagination
          page={page}
          offset={offset}
          changePage={changePage}
          position="bottom"
        />
      </div>
    </>
  );
}
function ResourcePagination({
  page,
  offset,
  changePage,
  position,
}: {
  page: Page;
  offset: number;
  changePage: (offset: number) => void;
  position: 'top' | 'bottom';
}) {
  return (
    <nav
      aria-label={`Resource pagination ${position}`}
      className="flex items-center gap-2 text-sm"
    >
      <span className="whitespace-nowrap text-text-secondary tabular-nums">
        {page.total ? (offset + 1).toLocaleString() : 0}–
        {Math.min(offset + page.items.length, page.total).toLocaleString()} of{' '}
        {page.total.toLocaleString()}
      </span>
      <ActionButton
        className={`${ui.secondary} px-3 py-1.5 text-sm`}
        disabled={offset === 0}
        onClick={() => changePage(Math.max(0, offset - page.limit))}
      >
        Previous
      </ActionButton>
      <ActionButton
        className={`${ui.secondary} px-3 py-1.5 text-sm`}
        disabled={offset + page.limit >= page.total}
        onClick={() => changePage(offset + page.limit)}
      >
        Next
      </ActionButton>
    </nav>
  );
}
export function ResourceDetail() {
  const [params] = useSearchParams();
  const { resourceId } = useParams();
  const id = decodeId(resourceId ?? '');
  const backParams = new URLSearchParams();
  for (const field of ['set_id', 'q', 'offset', 'filters']) {
    const value = params.get(field);
    if (value) backParams.set(field, value);
  }
  const returnTo = `/resources${backParams.size ? `?${backParams}` : ''}`;
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={returnTo}>
        ← Resources
      </Link>
      <ResourceRecord key={id} id={id} />
    </main>
  );
}
function ResourceRecord({ id }: { id: string }) {
  const [item, setItem] = useState<ResourceDetailData | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    request<ResourceDetailData>(resourceApiPath(id))
      .then((value) => {
        if (active) setItem(value);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [id]);
  if (error)
    return <p role="alert">Resource unavailable or outside your access.</p>;
  if (!item) return <p role="status">Loading Resource…</p>;
  return (
    <>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 flex-1 basis-80">
          <h1 className="mb-2 [overflow-wrap:anywhere]">
            {String(item.metadata.dct_title_s)}
          </h1>
          <p className={`${ui.code} !m-0`}>{item.id}</p>
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-3 text-sm">
          <span className={ui.badge}>{item.publication_state}</span>
          {item.set_id && (
            <Link
              className="text-active hover:underline"
              to={`/sets/${item.set_id}`}
            >
              {item.set_title}
            </Link>
          )}
          {item.can_associate && (
            <Link className={ui.secondary} to={`${resourcePath(item.id)}/set`}>
              {item.set_id ? 'Change managing Set' : 'Assign to a Set'}
            </Link>
          )}
        </div>
      </header>
      <div className="my-4 grid items-start gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="min-w-0 [&>section]:my-0">
          <ResourceEditor item={item} onSaved={setItem} />
        </div>
        <aside
          className="min-w-0 lg:sticky lg:top-24"
          aria-label="Resource preview panel"
        >
          <ResourcePreview id={item.id} version={item.lock_version} />
        </aside>
      </div>
      <details className={ui.notice}>
        <summary>Saved metadata JSON</summary>
        <pre className="max-w-xl whitespace-pre-wrap text-xs [overflow-wrap:anywhere]">
          {JSON.stringify(item.metadata, null, 2)}
        </pre>
      </details>
      {item.source_record && (
        <details className={ui.notice}>
          <summary>Import evidence and warnings</summary>
          <ul>
            {item.import_warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
          <pre className="max-w-xl whitespace-pre-wrap text-xs [overflow-wrap:anywhere]">
            {JSON.stringify(item.source_record, null, 2)}
          </pre>
        </details>
      )}
    </>
  );
}
