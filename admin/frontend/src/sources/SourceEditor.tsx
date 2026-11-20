import { encodeId, decodeId } from '../urlIds';
import { DetailTabs } from '../ui/DetailTabs';
import { ui } from '../ui/styles';
import { TextInput, TextArea, ActionButton } from '../ui/controls';
import { useEffect, useRef, useState } from 'react';
import {
  Link,
  useBeforeUnload,
  useBlocker,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router';
import { DiscardDialog } from '../ui/DiscardDialog';
import {
  ApiError,
  request,
  sourceBase,
  type Source,
  type SourceContract,
} from './api';
import { Load, SourceHistory, SourceResources } from './SourceBrowse';

export function SourcePage({
  mode = 'detail',
}: {
  mode?: 'detail' | 'edit' | 'create';
}) {
  const { sourceId: routeKey } = useParams();
  const sourceId = decodeId(routeKey ?? '');
  const [params] = useSearchParams();
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={`/sources?${params}`}>
        Back to Sources
      </Link>
      <Load<SourceContract>
        key={`${mode}:${sourceId}`}
        url={'/api/v1/admin/contracts/sources'}
      >
        {(contract) =>
          mode === 'create' ? (
            <SourceForm initial={null} contract={contract} />
          ) : (
            <Load<Source>
              url={`${sourceBase}/${encodeURIComponent(sourceId!)}`}
            >
              {(item) =>
                mode === 'edit' ? (
                  <SourceForm
                    key={item.source_id}
                    initial={item}
                    contract={contract}
                  />
                ) : (
                  <>
                    <header className="mb-4 flex flex-wrap items-center justify-between gap-4">
                      <div className="min-w-0 flex-1 basis-80">
                        <p className={ui.kicker}>Source</p>
                        <h1 className="[overflow-wrap:anywhere]">
                          {item.title}
                        </h1>
                        <p className="text-sm text-text-secondary">
                          Source ID: <code>{item.source_id}</code>
                          {item.legacy_code && (
                            <>
                              {' '}
                              · Legacy code: <code>{item.legacy_code}</code>
                            </>
                          )}{' '}
                          · Version {item.lock_version}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        {item.landing_page && (
                          <a
                            className={ui.secondary}
                            href={item.landing_page}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Visit website{' '}
                            <span className="sr-only">
                              (opens in a new tab)
                            </span>
                            ↗
                          </a>
                        )}
                        {contract.update && (
                          <Link
                            className={ui.primary}
                            to={`/sources/${encodeId(item.source_id)}/edit?${params}`}
                          >
                            Edit Source
                          </Link>
                        )}
                      </div>
                    </header>
                    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                      <div className="min-w-0">
                        <section
                          className={`${ui.panel} mb-4`}
                          aria-label="Source overview"
                        >
                          <h2>About this Source</h2>
                          <p className="max-w-4xl whitespace-pre-wrap text-sm leading-6 text-text-secondary [overflow-wrap:anywhere]">
                            {item.description || 'No description.'}
                          </p>
                          {item.landing_page ? (
                            <a
                              className="text-sm text-active [overflow-wrap:anywhere] hover:underline"
                              href={item.landing_page}
                            >
                              {item.landing_page}
                            </a>
                          ) : (
                            <p>No landing page.</p>
                          )}
                          <p className="mt-4 mb-0 text-xs text-text-secondary">
                            Last updated{' '}
                            <time dateTime={item.updated_at}>
                              {new Date(item.updated_at).toLocaleString()}
                            </time>
                          </p>
                        </section>
                        <details className={`${ui.panel} mb-4`}>
                          <summary className="cursor-pointer text-sm font-semibold">
                            Staff-only notes
                          </summary>
                          <p className="mt-4 mb-0 whitespace-pre-wrap text-sm leading-6 text-text-secondary [overflow-wrap:anywhere]">
                            {item.admin_notes || 'No staff notes.'}
                          </p>
                        </details>
                        {contract.set_read && (
                          <section
                            className={`${ui.panel} mb-4`}
                            aria-label="Source Sets"
                          >
                            <h2>Sets</h2>
                            <Link
                              className={ui.secondary}
                              to={`/sets?${new URLSearchParams({ source_id: item.source_id })}`}
                            >
                              Browse Sets for this Source
                            </Link>
                          </section>
                        )}
                      </div>
                      <DetailTabs
                        tabs={[
                          {
                            label: 'Activity Log',
                            content: contract.activity_read ? (
                              <SourceHistory
                                key={`history:${item.source_id}`}
                                id={item.source_id}
                              />
                            ) : (
                              <p>Source history requires additional access.</p>
                            ),
                          },
                          {
                            label: 'Browse Resources',
                            content: contract.resource_read ? (
                              <SourceResources
                                key={`resources:${item.source_id}`}
                                id={item.source_id}
                              />
                            ) : (
                              <p>
                                Resource browsing requires additional access.
                              </p>
                            ),
                          },
                        ]}
                      />
                    </div>
                  </>
                )
              }
            </Load>
          )
        }
      </Load>
    </main>
  );
}
const labels = {
  title: 'Title',
  legacy_code: 'Legacy code',
  description: 'Description',
  landing_page: 'Landing page',
  admin_notes: 'Staff-only notes',
};
type Fields = Record<keyof typeof labels, string>;
function fields(item: Source | null): Fields {
  return {
    title: item?.title ?? '',
    legacy_code: item?.legacy_code ?? '',
    description: item?.description ?? '',
    landing_page: item?.landing_page ?? '',
    admin_notes: item?.admin_notes ?? '',
  };
}
function SourceForm({
  initial,
  contract,
}: {
  initial: Source | null;
  contract: SourceContract;
}) {
  const [item, setItem] = useState(initial);
  const [draft, setDraft] = useState(() => fields(initial));
  const [id, setId] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [latest, setLatest] = useState<Source | null>(null);
  const [conflicted, setConflicted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState('');
  const summary = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const receipt = useRef<{ body: string; key: string } | null>(null);
  const allow = useRef(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const dirty =
    JSON.stringify(draft) !== JSON.stringify(fields(item)) ||
    (!item && id !== '');
  const blocker = useBlocker(() => (dirty || busy) && !allow.current);
  useBeforeUnload((event) => {
    if (dirty || busy) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  useEffect(() => {
    heading.current?.focus();
  }, []);
  useEffect(() => {
    if (error) summary.current?.focus();
  }, [error]);
  useEffect(() => {
    if (!dirty && !busy && blocker.state === 'blocked') blocker.proceed();
  }, [dirty, busy, blocker]);
  const changed = Object.keys(labels).filter(
    (name) => draft[name as keyof Fields] !== fields(item)[name as keyof Fields]
  ) as (keyof Fields)[];
  const canEdit = item ? contract.update : contract.create;
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved('');
    const values = {
      ...draft,
      landing_page: draft.landing_page || null,
      legacy_code: draft.legacy_code || null,
    };
    const body = JSON.stringify(
      item
        ? {
            ...Object.fromEntries(changed.map((name) => [name, values[name]])),
            lock_version: item.lock_version,
          }
        : { ...values, ...(id ? { source_id: id } : {}) }
    );
    if (receipt.current?.body !== body)
      receipt.current = { body, key: crypto.randomUUID() };
    try {
      const result = await request<Source>(
        item
          ? `${sourceBase}/${encodeURIComponent(item.source_id)}`
          : sourceBase,
        {
          method: item ? 'PATCH' : 'POST',
          body,
          headers: {
            'Content-Type': 'application/json',
            'X-GEOMG-Request': '1',
            'Idempotency-Key': receipt.current.key,
          },
        }
      );
      receipt.current = null;
      setItem(result);
      setDraft(fields(result));
      setLatest(null);
      setConflicted(false);
      setSaved('Source saved.');
      if (!item) {
        allow.current = true;
        navigate(`/sources/${encodeId(result.source_id)}?${params}`, {
          replace: true,
        });
      }
    } catch (failure) {
      if (failure instanceof ApiError && failure.code === 'stale_version')
        setConflicted(true);
      setError(
        failure instanceof ApiError
          ? failure
          : new ApiError('Save failed. Your draft is preserved.')
      );
    } finally {
      setBusy(false);
    }
  }
  async function compare() {
    setBusy(true);
    try {
      setLatest(
        await request<Source>(
          `${sourceBase}/${encodeURIComponent(item!.source_id)}`
        )
      );
    } catch (failure) {
      setError(failure as ApiError);
    } finally {
      setBusy(false);
    }
  }
  function adopt(keep: boolean) {
    const next = fields(latest!);
    if (keep) for (const name of changed) next[name] = draft[name];
    setDraft(next);
    setItem(latest);
    setLatest(null);
    setConflicted(false);
    setError(null);
    receipt.current = null;
  }
  return (
    <>
      <h1 ref={heading} tabIndex={-1}>
        {item ? 'Edit Source' : 'Create Source'}
      </h1>
      {item && (
        <p className="text-sm text-text-secondary">
          Source ID: <code>{item.source_id}</code> · Version {item.lock_version}
        </p>
      )}
      {!canEdit && (
        <p role="alert">
          You do not have permission to {item ? 'edit' : 'create'} Sources.
        </p>
      )}
      {error && (
        <div role="alert" className={ui.error} ref={summary} tabIndex={-1}>
          <h2>Changes need attention</h2>
          <p>{error.message}</p>
          {error.fields.length > 0 && (
            <ul>
              {error.fields.map((field, index) => (
                <li key={index}>
                  <a href={`#source-${field.field}`}>
                    {field.field}: {field.message}
                  </a>
                </li>
              ))}
            </ul>
          )}
          {conflicted && (
            <ActionButton
              disabled={busy}
              className={ui.secondary}
              onClick={compare}
            >
              Load latest for comparison
            </ActionButton>
          )}
        </div>
      )}
      {latest && (
        <section className={ui.notice} aria-label="Source conflict comparison">
          <h2>Review saved version {latest.lock_version}</h2>
          <dl className={ui.definitionList}>
            {changed.map((name) => (
              <div key={name}>
                <dt>{labels[name]}</dt>
                <dd>
                  Saved: {fields(latest)[name] || '(empty)'}
                  <br />
                  Your draft: {draft[name] || '(empty)'}
                </dd>
              </div>
            ))}
          </dl>
          <ActionButton className={ui.secondary} onClick={() => adopt(true)}>
            Keep my changes on latest version
          </ActionButton>
          <ActionButton className={ui.secondary} onClick={() => adopt(false)}>
            Discard my changes and use latest
          </ActionButton>
        </section>
      )}
      <div
        className={
          item
            ? 'grid items-start gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]'
            : ''
        }
      >
        <form
          className={`${ui.form} !mt-0 max-w-5xl [&_input]:h-10 [&_select]:h-10 [&_textarea]:h-24 [&_textarea]:min-h-24 [&_label]:leading-5 [&_small]:text-xs`}
          onSubmit={save}
          noValidate
        >
          <fieldset
            disabled={!canEdit || busy}
            className="grid grid-cols-1 items-start gap-x-5 gap-y-4 md:grid-cols-2"
          >
            <legend className="sr-only">Source fields</legend>
            {!item && (
              <div className={ui.field}>
                <label htmlFor="source-source_id">Source ID (optional)</label>
                <TextInput
                  id="source-source_id"
                  aria-describedby="source-id-help"
                  value={id}
                  maxLength={contract.fields.source_id.maxLength}
                  pattern={contract.fields.source_id.pattern}
                  onChange={(event) => setId(event.target.value)}
                />
                <small id="source-id-help">
                  Leave blank to generate an ID. The ID cannot be changed later.
                </small>
              </div>
            )}
            {(Object.keys(labels) as (keyof Fields)[]).map((name) => (
              <label
                className={`${ui.field} gap-1 ${['description', 'admin_notes', 'set_scope', 'landing_page', 'endpoint_url'].includes(name) ? 'md:col-span-2' : ''}`}
                key={name}
                htmlFor={`source-${name}`}
              >
                {labels[name]}
                {name === 'title' && ' (required)'}
                {name === 'description' || name === 'admin_notes' ? (
                  <TextArea
                    id={`source-${name}`}
                    value={draft[name]}
                    maxLength={contract.fields[name].maxLength}
                    rows={name === 'admin_notes' ? 8 : 5}
                    aria-invalid={
                      error?.fields.some((field) => field.field === name) ||
                      undefined
                    }
                    onChange={(event) => {
                      setDraft({ ...draft, [name]: event.target.value });
                      setSaved('');
                    }}
                  />
                ) : (
                  <TextInput
                    id={`source-${name}`}
                    value={draft[name]}
                    type={name === 'landing_page' ? 'url' : 'text'}
                    required={name === 'title'}
                    maxLength={contract.fields[name].maxLength}
                    aria-invalid={
                      error?.fields.some((field) => field.field === name) ||
                      undefined
                    }
                    onChange={(event) => {
                      setDraft({ ...draft, [name]: event.target.value });
                      setSaved('');
                    }}
                  />
                )}
              </label>
            ))}
          </fieldset>
          <div className={ui.actions}>
            <ActionButton
              className={ui.primary}
              disabled={!canEdit || busy || (!!item && !dirty)}
            >
              {busy ? 'Saving…' : 'Save Source'}
            </ActionButton>
            {item && (
              <Link
                className={ui.secondary}
                to={`/sources/${encodeId(item.source_id)}?${params}`}
              >
                View Source
              </Link>
            )}
          </div>
          {saved && <p role="status">{saved}</p>}
        </form>
        {item && contract.activity_read && (
          <div className="min-w-0">
            <SourceHistory key={item.lock_version} id={item.source_id} />
          </div>
        )}
      </div>
      {blocker.state === 'blocked' && (
        <DiscardDialog
          busy={busy}
          keep={() => blocker.reset()}
          discard={() => blocker.proceed()}
        />
      )}
    </>
  );
}
