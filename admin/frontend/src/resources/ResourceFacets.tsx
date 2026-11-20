import { ui } from '../ui/styles';
import { TextInput, SelectControl, ActionButton } from '../ui/controls';
import { Fragment, useEffect, useRef, useState } from 'react';
import { request } from '../sets/api';

type Selection = {
  include: string[];
  exclude: string[];
  operator: string;
  from?: string;
  to?: string;
};
const dateFields = [
  'last_harvested',
  'date_accessioned',
  'date_retired',
  'date_created',
];
type Facet = { field: string; label: string };
type Values = {
  items: {
    value: string;
    label: string;
    count: number;
    timestamp?: string | null;
  }[];
  more: boolean;
  total: number;
};
export function ResourceFacets({
  filters,
  q,
  setId,
  change,
}: {
  filters: string;
  q: string;
  setId: string;
  change: (value: string) => void;
}) {
  const [contract, setContract] = useState<Facet[]>([]);
  const [contractError, setContractError] = useState(false);
  const [findFacet, setFindFacet] = useState('');
  let selected: Record<string, Selection> = {};
  try {
    const parsed: unknown = JSON.parse(filters || '{}');
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      selected = Object.fromEntries(
        Object.entries(parsed).map(([name, value]) => {
          const selection = Array.isArray(value)
            ? { include: value }
            : (value ?? {});
          return [
            name,
            {
              include: Array.isArray(selection.include)
                ? selection.include
                : [],
              exclude: Array.isArray(selection.exclude)
                ? selection.exclude
                : [],
              operator: selection.operator ?? 'or',
              ...(selection.from ? { from: selection.from } : {}),
              ...(selection.to ? { to: selection.to } : {}),
            },
          ];
        })
      );
    }
  } catch {
    /* API reports invalid URL filters. */
  }
  useEffect(() => {
    request<Facet[]>('/api/v1/admin/resources/facets')
      .then((value) => {
        if (Array.isArray(value)) setContract(value);
      })
      .catch(() => setContractError(true));
  }, []);
  function save(next: Record<string, Selection>) {
    const compact = Object.fromEntries(
      Object.entries(next)
        .filter(
          ([, value]) =>
            value.include.length ||
            value.exclude.length ||
            value.from ||
            value.to
        )
        .map(([name, value]) => [
          name,
          value.from || value.to
            ? {
                ...(value.from ? { from: value.from } : {}),
                ...(value.to ? { to: value.to } : {}),
              }
            : !value.exclude.length && value.operator === 'or'
              ? value.include
              : value,
        ])
    );
    change(Object.keys(compact).length ? JSON.stringify(compact) : '');
  }
  function toggle(
    name: string,
    value: string,
    mode: 'include' | 'exclude' = 'include'
  ) {
    const current = selected[name] ?? {
      include: [],
      exclude: [],
      operator: 'or',
    };
    const opposite = mode === 'include' ? 'exclude' : 'include';
    save({
      ...selected,
      [name]: {
        ...current,
        from: undefined,
        to: undefined,
        [mode]: current[mode].includes(value)
          ? current[mode].filter((item) => item !== value)
          : [...current[mode], value],
        [opposite]: current[opposite].filter((item) => item !== value),
      },
    });
  }
  return (
    <section className="min-w-0" aria-label="Resource filters">
      <div className="min-w-0">
        <h2 className="m-0 p-4 text-base font-semibold text-primary">
          Refine results
        </h2>
        <div className="flex flex-wrap gap-2 px-4 pb-4 empty:hidden">
          {Object.entries(selected).flatMap(([name, selection]) =>
            (['include', 'exclude'] as const).flatMap((mode) =>
              selection[mode].map((value) => (
                <ActionButton
                  className="rounded-md border border-active/30 bg-active-soft px-2 py-1 text-left text-xs font-medium text-primary [overflow-wrap:anywhere] hover:bg-active/10"
                  key={`${name}:${mode}:${value}`}
                  onClick={() => toggle(name, value, mode)}
                  aria-label={`Remove ${mode === 'exclude' ? 'exclusion ' : ''}${name}: ${value}`}
                >
                  {mode === 'exclude' ? 'Not: ' : ''}
                  {contract.find((item) => item.field === name)?.label ??
                    name}:{' '}
                  {name === 'imports' && value.length === 36
                    ? value.slice(0, 8)
                    : value}{' '}
                  ×
                </ActionButton>
              ))
            )
          )}
          {Object.keys(selected).length > 0 && (
            <ActionButton
              className="rounded-md border border-active/30 bg-active-soft px-2 py-1 text-left text-xs font-medium text-primary [overflow-wrap:anywhere] hover:bg-active/10"
              onClick={() => change('')}
            >
              Clear all
            </ActionButton>
          )}
        </div>
        {Object.entries(selected)
          .filter(([, value]) => value.from || value.to)
          .map(([field, value]) => (
            <ActionButton
              key={field}
              className="mx-4 mb-3 rounded-md bg-active-soft px-2 py-1 text-xs text-primary"
              onClick={() => {
                const next = { ...selected };
                delete next[field];
                save(next);
              }}
            >
              {contract.find((item) => item.field === field)?.label}:{' '}
              {value.from || 'Any'} – {value.to || 'Now'} ×
            </ActionButton>
          ))}
        <div className="px-4 pb-3">
          <TextInput
            type="search"
            aria-label="Find a filter"
            placeholder="Find a filter…"
            className="h-9 text-sm"
            value={findFacet}
            onChange={(event) => setFindFacet(event.target.value)}
          />
        </div>
        {contract
          .filter((facet) =>
            facet.label.toLowerCase().includes(findFacet.toLowerCase())
          )
          .map((facet) => (
            <Fragment key={facet.field}>
              <FacetGroup
                facet={facet}
                filters={filters}
                q={q}
                setId={setId}
                selected={selected[facet.field]?.include ?? []}
                excluded={selected[facet.field]?.exclude ?? []}
                exclude={(value) => toggle(facet.field, value, 'exclude')}
                operator={selected[facet.field]?.operator ?? 'or'}
                setOperator={(operator) =>
                  save({
                    ...selected,
                    [facet.field]: { ...selected[facet.field], operator },
                  })
                }
                toggle={(value) => toggle(facet.field, value)}
              />
              {facet.field === 'imports' && (
                <DateRangeFilter
                  key={filters}
                  contract={contract}
                  selected={selected}
                  apply={(field, from, to) =>
                    save({
                      ...selected,
                      [field]: {
                        include: [],
                        exclude: [],
                        operator: 'or',
                        ...(from ? { from } : {}),
                        ...(to ? { to } : {}),
                      },
                    })
                  }
                />
              )}
            </Fragment>
          ))}
        {contractError && (
          <p role="alert" className="px-4 text-sm">
            Filters unavailable. Reload to retry.
          </p>
        )}
        {!contract.length && !contractError && (
          <p role="status" className="px-4 text-sm">
            Loading filters…
          </p>
        )}
        {contract.length > 0 &&
          !contract.some((facet) =>
            facet.label.toLowerCase().includes(findFacet.toLowerCase())
          ) && <p className="px-4 text-sm">No matching filters.</p>}
      </div>
    </section>
  );
}
function FacetGroup({
  operator,
  setOperator,
  facet,
  filters,
  q,
  setId,
  selected,
  excluded,
  exclude,
  toggle,
}: {
  facet: Facet;
  operator: string;
  setOperator: (value: string) => void;
  filters: string;
  q: string;
  setId: string;
  selected: string[];
  excluded: string[];
  exclude: (value: string) => void;
  toggle: (value: string) => void;
}) {
  const [open, setOpen] = useState(
    ['imports', 'resource_class', 'provider'].includes(facet.field) ||
      selected.length + excluded.length > 0
  );
  return (
    <details
      className="group border-t border-border"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="flex list-none items-center gap-2 px-4 py-3 text-sm font-semibold text-primary hover:bg-surface-subtle [&::-webkit-details-marker]:hidden">
        {facet.label}
        {selected.length + excluded.length > 0 && (
          <span className="rounded-full bg-active px-1.5 py-0.5 text-xs text-white">
            {selected.length + excluded.length}
          </span>
        )}
        <span
          aria-hidden="true"
          className="ml-auto -rotate-90 text-text-secondary group-open:rotate-0"
        >
          ⌄
        </span>
      </summary>
      {open && (
        <div
          data-facet-panel
          className="px-4 pb-4"
          role="group"
          aria-label={`${facet.label} filters`}
        >
          {selected.length > 1 && (
            <label className="mb-3 flex flex-wrap items-center gap-2 text-xs [&_select]:w-auto">
              Match included values
              <SelectControl
                aria-label={`Match included ${facet.label}`}
                value={operator}
                onChange={(event) => setOperator(event.target.value)}
              >
                <option value="or">Any</option>
                <option value="and">All</option>
              </SelectControl>
            </label>
          )}
          <FacetValues
            field={facet.field}
            label={facet.label}
            {...{
              filters,
              q,
              setId,
              selected,
              excluded,
              exclude,
              toggle,
            }}
          />
        </div>
      )}
    </details>
  );
}

type ValueProps = {
  field: string;
  label: string;
  filters: string;
  q: string;
  setId: string;
  selected: string[];
  excluded: string[];
  exclude: (value: string) => void;
  toggle: (value: string) => void;
};

function FacetValues(props: ValueProps) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <FacetOptions
        {...props}
        term=""
        offset={0}
        sort={
          props.field === 'imports' || dateFields.includes(props.field)
            ? 'recent'
            : 'count_desc'
        }
        more={() => setExpanded(true)}
      />
      {expanded && <FacetModal {...props} close={() => setExpanded(false)} />}
    </>
  );
}

function FacetModal(props: ValueProps & { close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const results = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState('');
  const [term, setTerm] = useState('');
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState(
    props.field === 'imports' || dateFields.includes(props.field)
      ? 'recent'
      : 'count_desc'
  );
  useEffect(() => {
    const previous = document.activeElement;
    const panel = dialog.current?.closest('[data-facet-panel]');
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog.current?.showModal();
    return () => {
      document.body.style.overflow = overflow;
      const opener = panel?.querySelector<HTMLElement>('[data-facet-more]');
      if (opener) opener.focus();
      else if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-4xl overflow-y-auto rounded-xl border border-border bg-surface text-text-primary shadow-xl backdrop:bg-primary-dark/50 [&>p]:px-6"
      aria-labelledby={`facet-title-${props.field}`}
      aria-describedby={`facet-description-${props.field}`}
      onCancel={props.close}
    >
      <header className="flex items-start justify-between gap-4 border-b border-border bg-surface-subtle p-5 sm:p-6 [&_h2]:mb-0 [&_p]:mt-2 [&_p]:mb-0 [&_p]:text-sm [&_p]:text-text-secondary">
        <div>
          <h2 id={`facet-title-${props.field}`}>
            More options for {props.label}
          </h2>
          <p id={`facet-description-${props.field}`}>
            Explore additional facet values to refine your search.
          </p>
        </div>
        <ActionButton
          type="button"
          className="inline-flex size-10 shrink-0 items-center justify-center rounded-md text-3xl text-text-secondary hover:bg-surface-muted"
          aria-label="Close facet options"
          onClick={props.close}
        >
          ×
        </ActionButton>
      </header>
      <form
        className="flex flex-wrap items-center gap-3 px-5 py-4 sm:px-6"
        onSubmit={(event) => {
          event.preventDefault();
          setTerm(input.trim());
          setOffset(0);
        }}
      >
        <label className="min-w-44 flex-1">
          <span className="sr-only">Find facet values</span>
          <TextInput
            type="search"
            placeholder="Search within facet values"
            value={input}
            onChange={(event) => setInput(event.target.value)}
          />
        </label>
        <ActionButton className={ui.primary}>Filter</ActionButton>
        <ActionButton
          type="button"
          className={ui.secondary}
          onClick={() => {
            setInput('');
            setTerm('');
            setOffset(0);
          }}
        >
          Reset
        </ActionButton>
        <label className="flex flex-wrap items-center gap-2">
          Sort by{' '}
          <SelectControl
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setOffset(0);
            }}
          >
            {(props.field === 'imports' ||
              dateFields.includes(props.field)) && (
              <option value="recent">Newest first</option>
            )}
            <option value="count_desc">Result Count (High → Low)</option>
            <option value="count_asc">Result Count (Low → High)</option>
            <option value="alpha_asc">Facet Value (A → Z)</option>
            <option value="alpha_desc">Facet Value (Z → A)</option>
          </SelectControl>
        </label>
      </form>
      <div
        className="px-5 pb-5 sm:px-6"
        ref={results}
        tabIndex={-1}
        aria-label="Facet values page"
      >
        <FacetOptions
          {...props}
          {...{ term, offset, sort }}
          setOffset={(next) => {
            results.current?.focus();
            setOffset(next);
          }}
        />
      </div>
    </dialog>
  );
}

function FacetOptions(
  props: ValueProps & {
    term: string;
    offset: number;
    sort: string;
    more?: () => void;
    setOffset?: (value: number) => void;
  }
) {
  const { field, filters, q, setId, term, offset, sort } = props;
  // Counts ignore this facet's own selections. Keep its rows mounted when
  // toggling them so keyboard focus survives and no redundant read is needed.
  let countFilters = filters || '{}';
  try {
    const parsed = JSON.parse(countFilters);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      delete parsed[field];
      countFilters = JSON.stringify(parsed);
    }
  } catch {
    /* Preserve invalid input for the API's validation response. */
  }
  const url = `/api/v1/admin/resources/facets/${field}?${new URLSearchParams({ q, filters: countFilters, term, offset: String(offset), limit: field === 'imports' ? '20' : '10', sort, ...(setId ? { set_id: setId } : {}) })}`;
  return <FacetPage key={url} {...props} url={url} />;
}

function FacetPage({
  url,
  field,
  selected,
  excluded,
  toggle,
  exclude,
  more,
  offset,
  setOffset,
}: ValueProps & {
  url: string;
  more?: () => void;
  offset: number;
  setOffset?: (value: number) => void;
}) {
  const [data, setData] = useState<Values | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    request<Values>(url)
      .then((value) => {
        if (active) setData(value);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [url]);
  if (error)
    return (
      <p role="alert">
        Facet values unavailable. Close and reopen this filter to retry.
      </p>
    );
  if (!data) return <p role="status">Loading facet counts…</p>;
  return (
    <>
      <div
        className={`grid gap-1 ${field === 'imports' ? 'max-h-64 overflow-y-auto overscroll-contain pr-1' : ''}`}
      >
        {data.items.slice(0, field === 'imports' ? 20 : 10).map((item) => (
          <div className="flex items-center gap-2" key={item.value}>
            <ActionButton
              type="button"
              className="min-w-0 flex-1 rounded-md px-2 py-1.5 text-left text-sm text-text-secondary hover:bg-surface-muted aria-pressed:bg-active-soft aria-pressed:font-semibold aria-pressed:text-active"
              aria-label={`${item.label} (${item.count})`}
              aria-pressed={selected.includes(item.value)}
              onClick={() => toggle(item.value)}
            >
              <span className="flex items-start gap-2">
                <span
                  aria-hidden="true"
                  className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded border border-control text-xs"
                >
                  {selected.includes(item.value) ? '✓' : ''}
                </span>
                <span
                  className={`min-w-0 flex-1 ${field === 'imports' ? 'text-xs' : '[overflow-wrap:anywhere]'}`}
                >
                  {field === 'imports' &&
                  /^[0-9a-f]{8}-[0-9a-f-]{27}$/.test(item.label)
                    ? `Import ${item.label.slice(0, 8)}`
                    : item.label}
                  {field === 'imports' && item.timestamp && (
                    <time
                      dateTime={item.timestamp}
                      title={new Date(item.timestamp).toLocaleString()}
                      className="mt-0.5 block text-xs font-normal text-text-muted"
                    >
                      {relativeTime(item.timestamp)}
                    </time>
                  )}
                </span>
                <span className="rounded bg-surface-muted px-1.5 text-xs leading-5 text-text-secondary tabular-nums">
                  {item.count.toLocaleString()}
                </span>
              </span>
            </ActionButton>
            <ActionButton
              type="button"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-md text-text-secondary hover:bg-danger-soft hover:text-danger aria-pressed:bg-danger-soft aria-pressed:text-danger aria-pressed:ring-1 aria-pressed:ring-danger"
              aria-label={`Exclude ${item.label}`}
              title={`Exclude ${item.label}`}
              aria-pressed={excluded.includes(item.value)}
              onClick={() => exclude(item.value)}
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M8 12h8" />
              </svg>
            </ActionButton>
          </div>
        ))}
        {!data.items.length && <p>No matching values.</p>}
      </div>
      {more ? (
        data.more && (
          <ActionButton
            type="button"
            data-facet-more
            className="py-2 text-sm font-medium text-active hover:text-active-hover hover:underline"
            onClick={more}
          >
            More »
          </ActionButton>
        )
      ) : (
        <footer className="flex flex-wrap items-center gap-3 border-t border-border bg-surface-subtle px-5 py-4 sm:px-6 [&_p]:mb-0 [&_p]:flex-1 [&_p]:text-sm [&_p]:text-text-secondary">
          <p role="status">
            Showing page {offset / (field === 'imports' ? 20 : 10) + 1} of{' '}
            {Math.max(
              1,
              Math.ceil(data.total / (field === 'imports' ? 20 : 10))
            )}{' '}
            · {data.total?.toLocaleString()} total values
          </p>
          <ActionButton
            className={ui.secondary}
            disabled={!offset}
            onClick={() =>
              setOffset?.(Math.max(0, offset - (field === 'imports' ? 20 : 10)))
            }
          >
            Previous
          </ActionButton>
          <ActionButton
            className={ui.secondary}
            disabled={!data.more}
            onClick={() =>
              setOffset?.(offset + (field === 'imports' ? 20 : 10))
            }
          >
            Next
          </ActionButton>
        </footer>
      )}
    </>
  );
}

function relativeTime(timestamp: string) {
  const days = Math.max(
    0,
    Math.floor((Date.now() - new Date(timestamp).getTime()) / 86400000)
  );
  return days === 0
    ? 'Today'
    : days === 1
      ? 'Yesterday'
      : `${days.toLocaleString()} days ago`;
}

function DateRangeFilter({
  contract,
  selected,
  apply,
}: {
  contract: Facet[];
  selected: Record<string, Selection>;
  apply: (field: string, from: string, to: string) => void;
}) {
  const existing = Object.keys(selected).find(
    (field) => selected[field].from || selected[field].to
  );
  const [field, setField] = useState(existing ?? 'date_created');
  const [from, setFrom] = useState(
    existing ? (selected[existing].from ?? '') : ''
  );
  const [to, setTo] = useState(existing ? (selected[existing].to ?? '') : '');
  if (!contract.some((item) => dateFields.includes(item.field))) return null;
  return (
    <details className="group border-t border-border" open={!!existing}>
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-primary">
        Date range filter
      </summary>
      <form
        className="grid gap-2 px-4 pb-4 text-xs"
        onSubmit={(event) => {
          event.preventDefault();
          apply(field, from, to);
        }}
      >
        <label>
          Date field
          <SelectControl
            className="mt-1 h-9 text-sm"
            value={field}
            onChange={(event) => setField(event.target.value)}
          >
            {contract
              .filter((item) => dateFields.includes(item.field))
              .map((item) => (
                <option key={item.field} value={item.field}>
                  {item.label}
                </option>
              ))}
          </SelectControl>
        </label>
        <label>
          From
          <TextInput
            className="mt-1 h-9 text-sm"
            aria-label="From date"
            type="date"
            value={from}
            max={to || '9998-12-31'}
            onChange={(event) => setFrom(event.target.value)}
          />
        </label>
        <label>
          Through
          <TextInput
            className="mt-1 h-9 text-sm"
            aria-label="Through date"
            type="date"
            value={to}
            min={from}
            max="9998-12-31"
            onChange={(event) => setTo(event.target.value)}
          />
        </label>
        <span className="text-text-muted">Inclusive dates · UTC</span>
        <ActionButton className={ui.primary} disabled={!from && !to}>
          Apply dates
        </ActionButton>
      </form>
    </details>
  );
}
