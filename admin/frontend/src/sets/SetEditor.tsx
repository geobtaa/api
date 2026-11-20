import { showWorkManagement } from '../config/features';
import { encodeId, decodeId } from '../urlIds';
import { SetActions } from './SetActions';
import { ui } from '../ui/styles';
import {
  TextInput,
  TextArea,
  SelectControl,
  ActionButton,
} from '../ui/controls';
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
  setBase,
  type SetRecord,
  type SetContract,
} from './api';
import { Load } from '../sources/SourceBrowse';
import { SourcePicker } from '../sources/SourcePicker';
import { SetHistory } from './SetBrowse';
import { WorkflowCatalogSelect } from '../workflows/WorkflowCatalogSelect';
export function SetPage({
  mode = 'detail',
}: {
  mode?: 'detail' | 'edit' | 'create';
}) {
  const { setId: routeKey } = useParams();
  const setId = decodeId(routeKey ?? '');
  const [revision, setRevision] = useState(0);
  const [params] = useSearchParams();
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={`/sets?${params}`}>
        Back to Sets
      </Link>
      <Load<SetContract>
        key={`${mode}:${setId}`}
        url={'/api/v1/admin/contracts/sets'}
      >
        {(contract) =>
          mode === 'create' ? (
            <SetForm initial={null} contract={contract} />
          ) : (
            <Load<SetRecord>
              key={revision}
              url={`${setBase}/${encodeURIComponent(setId!)}`}
            >
              {(item) =>
                mode === 'edit' ? (
                  <SetForm
                    key={item.set_id}
                    initial={item}
                    contract={contract}
                  />
                ) : (
                  <>
                    <p className={ui.kicker}>Set</p>
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                      <h1 className="m-0 min-w-0 flex-1 basis-80">
                        {item.title}
                      </h1>
                      <SetActions
                        item={item}
                        contract={contract}
                        changed={() => setRevision((value) => value + 1)}
                      />
                      {contract.update && item.status !== 'retired' && (
                        <Link
                          className={ui.secondary}
                          to={`/sets/${encodeId(item.set_id)}/edit?${params}`}
                        >
                          Edit Set
                        </Link>
                      )}
                    </div>
                    <div className="mb-4 flex flex-wrap gap-2">
                      <Link
                        className={ui.secondary}
                        to={`/resources?set_id=${encodeURIComponent(item.set_id)}`}
                      >
                        Resources ({item.resource_count ?? 0})
                      </Link>
                      {contract.workflow_read && (
                        <Link
                          className={ui.secondary}
                          to={`/sets/${encodeId(item.set_id)}/workflows`}
                        >
                          Workflows
                        </Link>
                      )}
                      {contract.representative_update &&
                        item.status !== 'retired' && (
                          <Link
                            className={ui.secondary}
                            to={`/sets/${encodeId(item.set_id)}/representative`}
                          >
                            Choose representative
                          </Link>
                        )}

                      {showWorkManagement && (
                        <>
                          <Link
                            className={ui.secondary}
                            to={`/work?set_id=${encodeURIComponent(item.set_id)}`}
                          >
                            Work Queue
                          </Link>
                          <Link
                            className={ui.secondary}
                            to={`/sets/${encodeId(item.set_id)}/maintenance`}
                          >
                            Maintenance
                          </Link>
                        </>
                      )}
                    </div>
                    <p>
                      Set ID: <code>{item.set_id}</code> · Version{' '}
                      {item.lock_version}
                    </p>
                    <p className="text-sm text-text-secondary">
                      Source:{' '}
                      <Link to={`/sources/${encodeId(item.source_id)}`}>
                        {item.source_id}
                      </Link>
                    </p>
                    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
                      <div className="min-w-0">
                        <dl className="m-0 grid gap-x-5 gap-y-4 rounded-lg border border-border bg-surface p-4 sm:grid-cols-2 [&_dt]:mb-1 [&_dt]:text-xs [&_dt]:font-semibold [&_dt]:text-text-secondary [&_dd]:m-0 [&_dd]:text-sm">
                          {(
                            [
                              'legacy_code',
                              'review_interval',
                              'workflow_catalog_id',
                              'harvest_interval',
                              'endpoint_url',
                              'endpoint_description',
                              'tags',
                              'set_scope',
                              'description',
                              'admin_notes',
                            ] as (keyof Fields)[]
                          )
                            .filter((name) => !item || name !== 'status')
                            .map((name) => (
                              <div
                                key={name}
                                className={
                                  [
                                    'description',
                                    'admin_notes',
                                    'set_scope',
                                  ].includes(name)
                                    ? 'sm:col-span-2'
                                    : undefined
                                }
                              >
                                <dt>
                                  {name === 'tags' ? 'Tags' : labels[name]}
                                </dt>
                                <dd className="whitespace-pre-wrap [overflow-wrap:anywhere]">
                                  {item[name] ||
                                    (name === 'workflow_catalog_id'
                                      ? item.workflow || '—'
                                      : '—')}
                                </dd>
                              </div>
                            ))}
                        </dl>
                        <p>
                          Workflow and interval labels describe intended work.
                          They do not start work or establish a schedule.
                        </p>
                      </div>
                      <div className="min-w-0">
                        {contract.activity_read ? (
                          <SetHistory key={item.set_id} id={item.set_id} />
                        ) : (
                          <p>Set history requires additional access.</p>
                        )}
                      </div>
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
  set_scope: 'Set scope',
  status: 'Status',
  description: 'Description',
  endpoint_url: 'Endpoint URL',
  endpoint_description: 'Endpoint description',
  workflow_catalog_id: 'Workflow',
  review_interval: 'Review interval',
  harvest_interval: 'Harvest interval',
  tags: 'Tags (pipe-separated)',
  admin_notes: 'Staff-only notes',
};
type Fields = Record<keyof typeof labels, string>;
function fields(item: SetRecord | null, contract: SetContract): Fields {
  return {
    title: item?.title ?? '',
    legacy_code: item?.legacy_code ?? '',
    set_scope: item?.set_scope ?? '',
    status: item?.status ?? contract.fields.status.default ?? '',
    description: item?.description ?? '',
    endpoint_url: item?.endpoint_url ?? '',
    endpoint_description: item?.endpoint_description ?? '',
    workflow_catalog_id: item?.workflow_catalog_id ?? '',
    review_interval: item?.review_interval ?? '',
    harvest_interval: item?.harvest_interval ?? '',
    tags: item?.tags ?? '',
    admin_notes: item?.admin_notes ?? '',
  };
}
function SetForm({
  initial,
  contract,
}: {
  initial: SetRecord | null;
  contract: SetContract;
}) {
  const [item, setItem] = useState(initial);
  const [draft, setDraft] = useState(() => fields(initial, contract));
  const [params] = useSearchParams();
  const [source, setSource] = useState<string | null>(
    initial?.source_id ?? params.get('source_id')
  );
  const [id, setId] = useState('');
  const [error, setError] = useState<ApiError | null>(null);
  const [latest, setLatest] = useState<SetRecord | null>(null);
  const [conflicted, setConflicted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState('');
  const summary = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const receipt = useRef<{ body: string; key: string } | null>(null);
  const allow = useRef(false);
  const navigate = useNavigate();
  const dirty =
    JSON.stringify(draft) !== JSON.stringify(fields(item, contract)) ||
    (!item && (id !== '' || source !== null));
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
    (name) =>
      draft[name as keyof Fields] !==
      fields(item, contract)[name as keyof Fields]
  ) as (keyof Fields)[];
  const canEdit = item
    ? contract.update && item.status !== 'retired'
    : contract.create;
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved('');
    const values = {
      ...draft,
      endpoint_url: draft.endpoint_url || null,
      workflow_catalog_id: draft.workflow_catalog_id || null,
    };
    const body = JSON.stringify(
      item
        ? {
            ...Object.fromEntries(changed.map((name) => [name, values[name]])),
            lock_version: item.lock_version,
          }
        : { ...values, source_id: source, ...(id ? { set_id: id } : {}) }
    );
    if (receipt.current?.body !== body)
      receipt.current = { body, key: crypto.randomUUID() };
    try {
      const result = await request<SetRecord>(
        item ? `${setBase}/${encodeURIComponent(item.set_id)}` : setBase,
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
      setDraft(fields(result, contract));
      setLatest(null);
      setConflicted(false);
      setSaved('Set saved.');
      if (!item) {
        allow.current = true;
        navigate(`/sets/${encodeId(result.set_id)}?${params}`, {
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
        await request<SetRecord>(
          `${setBase}/${encodeURIComponent(item!.set_id)}`
        )
      );
    } catch (failure) {
      setError(failure as ApiError);
    } finally {
      setBusy(false);
    }
  }
  function adopt(keep: boolean) {
    const next = fields(latest!, contract);
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
        {item ? 'Edit Set' : 'Create Set'}
      </h1>
      {item && (
        <p className="text-sm text-text-secondary">
          Set ID: <code>{item.set_id}</code> · Version {item.lock_version}
        </p>
      )}
      {!canEdit && (
        <p role="alert">
          {item?.status === 'retired'
            ? 'Restore this Set before editing.'
            : `You do not have permission to ${item ? 'edit' : 'create'} Sets.`}
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
                  <a href={`#set-${field.field}`}>
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
        <section className={ui.notice} aria-label="Set conflict comparison">
          <h2>Review saved version {latest.lock_version}</h2>
          <dl className={ui.definitionList}>
            {changed.map((name) => (
              <div key={name}>
                <dt>{labels[name]}</dt>
                <dd>
                  Saved: {fields(latest, contract)[name] || '(empty)'}
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
            <legend className="sr-only">Set fields</legend>
            {item ? (
              <p className="m-0 md:col-span-2">
                Source:{' '}
                <Link to={`/sources/${encodeId(item.source_id)}`}>
                  {item.source_id}
                </Link>
              </p>
            ) : (
              <div id="set-source_id" tabIndex={-1} className="md:col-span-2">
                <p>
                  A Source is required. The Source cannot be changed after
                  creation.
                </p>
                <SourcePicker
                  value={source}
                  saved={null}
                  canRead={true}
                  canUse={canEdit}
                  change={setSource}
                />
              </div>
            )}
            {!item && (
              <div className={ui.field}>
                <label htmlFor="set-set_id">Set ID (optional)</label>
                <TextInput
                  id="set-set_id"
                  aria-describedby="set-id-help"
                  value={id}
                  maxLength={contract.fields.set_id.maxLength}
                  pattern={contract.fields.set_id.pattern}
                  onChange={(event) => setId(event.target.value)}
                />
                <small id="set-id-help">
                  Leave blank to generate an ID. The ID cannot be changed later.
                </small>
              </div>
            )}
            {(
              [
                'title',
                'review_interval',
                'legacy_code',
                'harvest_interval',
                'workflow_catalog_id',
                'status',
                'endpoint_url',
                'endpoint_description',
                'tags',
                'set_scope',
                'description',
                'admin_notes',
              ] as (keyof Fields)[]
            )
              .filter((name) => !item || name !== 'status')
              .map((name) => (
                <div
                  className={`${ui.field} gap-1 ${['description', 'admin_notes', 'set_scope', 'landing_page', 'endpoint_url'].includes(name) ? 'md:col-span-2' : ''}`}
                  key={name}
                >
                  <label htmlFor={`set-${name}`}>
                    {labels[name]}
                    {name === 'title' && ' (required)'}
                  </label>
                  {name === 'workflow_catalog_id' ? (
                    <WorkflowCatalogSelect
                      id={`set-${name}`}
                      value={draft[name]}
                      legacy={item?.workflow}
                      onChange={(value) => {
                        setDraft({ ...draft, [name]: value ?? '' });
                        setSaved('');
                      }}
                    />
                  ) : name === 'status' ? (
                    <SelectControl
                      aria-invalid={
                        error?.fields.some((field) => field.field === name) ||
                        undefined
                      }
                      id={`set-${name}`}
                      aria-describedby={
                        contract.fields[name]?.description
                          ? `set-${name}-help`
                          : undefined
                      }
                      value={draft[name]}
                      onChange={(event) => {
                        setDraft({ ...draft, [name]: event.target.value });
                        setSaved('');
                      }}
                    >
                      {contract.fields.status.enum?.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </SelectControl>
                  ) : name === 'description' ||
                    name === 'admin_notes' ||
                    name === 'set_scope' ? (
                    <TextArea
                      id={`set-${name}`}
                      aria-describedby={
                        contract.fields[name]?.description
                          ? `set-${name}-help`
                          : undefined
                      }
                      value={draft[name]}
                      maxLength={contract.fields[name]?.maxLength}
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
                      id={`set-${name}`}
                      aria-describedby={
                        contract.fields[name]?.description
                          ? `set-${name}-help`
                          : undefined
                      }
                      value={draft[name]}
                      type={name === 'endpoint_url' ? 'url' : 'text'}
                      required={name === 'title'}
                      maxLength={contract.fields[name]?.maxLength}
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
                  {contract.fields[name]?.description && (
                    <small id={`set-${name}-help`}>
                      {contract.fields[name].description}
                    </small>
                  )}
                </div>
              ))}
          </fieldset>
          <div className={ui.actions}>
            <ActionButton
              className={ui.primary}
              disabled={!canEdit || busy || (!!item && !dirty)}
            >
              {busy ? 'Saving…' : 'Save Set'}
            </ActionButton>
            {item && (
              <Link
                className={ui.secondary}
                to={`/sets/${encodeId(item.set_id)}?${params}`}
              >
                View Set
              </Link>
            )}
          </div>
          {saved && <p role="status">{saved}</p>}
        </form>
        {item && contract.activity_read && (
          <div className="min-w-0">
            <SetHistory key={item.lock_version} id={item.set_id} />
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
