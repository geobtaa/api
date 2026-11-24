import { ui } from '../ui/styles';
import { TextInput, SelectControl, ActionButton } from '../ui/controls';
import { useEffect, useRef, useState } from 'react';
import { ApiError, request, type Page } from '../sets/api';

const base = '/api/v1/admin/workflows';
interface Process {
  position: number;
  process_type: string;
  name: string;
  configuration_schema_version: number;
  configuration: Record<string, string | null>;
}
interface Editable extends Process {
  localId: string;
}
interface Version {
  version_id: string;
  number: number;
  state: string;
  checksum: string | null;
  processes: Process[];
}
interface Summary {
  workflow_id: string;
  title: string;
  lock_version: number;
}
interface Workflow extends Summary {
  active: Version | null;
  draft: Version | null;
  can_change: boolean;
  can_activate: boolean;
}
interface Contract {
  process_types: {
    key: string;
    label: string;
    definition: string;
    configuration_fields: string[];
  }[];
  configuration_schema: {
    properties: Record<string, { title: string; description?: string }>;
  };
  maximum_processes: number;
  configuration_schema_version: number;
  can_create: boolean;
}
function editable(processes: Process[]): Editable[] {
  return processes.map((p) => ({
    ...p,
    localId: crypto.randomUUID(),
    configuration: Object.fromEntries(
      Object.entries(p.configuration).filter(([, value]) => value !== null)
    ),
  }));
}
function wire(processes: Editable[]): Process[] {
  return processes.map((process, index) => ({
    position: index + 1,
    name: process.name,
    process_type: process.process_type,
    configuration_schema_version: process.configuration_schema_version,
    configuration: process.configuration,
  }));
}

export function WorkflowPanel({
  setId,
  retired,
  disabled,
  onBusy,
  onDirty,
  onChanged,
}: {
  setId: string;
  retired: boolean;
  disabled: boolean;
  onBusy: (busy: boolean) => void;
  onDirty: (dirty: boolean) => void;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [contract, setContract] = useState<Contract | null>(null);
  const [page, setPage] = useState<Page<Summary> | null>(null);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [readRetry, setReadRetry] = useState(0);
  const [selected, setSelected] = useState('');
  const [item, setItem] = useState<Workflow | null>(null);
  const [draft, setDraft] = useState<Editable[]>([]);
  const [baseline, setBaseline] = useState('[]');
  const [title, setTitle] = useState('');
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [comparison, setComparison] = useState<Workflow | null>(null);
  const receipt = useRef<{ signature: string; key: string } | null>(null);
  const errorBox = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const dirty = !!title || JSON.stringify(wire(draft)) !== baseline;
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);
  useEffect(() => {
    if (error) errorBox.current?.focus();
  }, [error]);
  useEffect(() => {
    if (!open) return;
    let active = true;
    Promise.all([
      request<Contract>('/api/v1/admin/contracts/workflows'),
      request<Page<Summary>>(
        `${base}?${new URLSearchParams({ set_id: setId, offset: String(offset), limit: '20' })}`
      ),
    ])
      .then(([c, p]) => {
        if (active) {
          setContract(c);
          setPage(p);
        }
      })
      .catch((e: Error) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
    };
  }, [open, setId, offset, refresh]);
  const loadedId = item?.workflow_id;
  useEffect(() => {
    if (!selected || loadedId === selected) return;
    let active = true;
    request<Workflow>(`${base}/${selected}`)
      .then((value) => {
        if (active) adopt(value);
      })
      .catch((e: Error) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
    };
  }, [selected, loadedId, readRetry]);

  function working(value: boolean) {
    setBusy(value);
    onBusy(value);
  }
  function adopt(value: Workflow, preserve = false) {
    setItem(value);
    const next = editable(value.draft?.processes ?? []);
    if (!preserve) setDraft(next);
    setBaseline(JSON.stringify(wire(next)));
    setConfirmed(false);
    setComparison(null);
    setError(null);
  }
  function edit(next: Editable[]) {
    setDraft(next);
    setConfirmed(false);
    setMessage('');
  }
  async function mutate(path: string, method: string, payload: object) {
    working(true);
    setError(null);
    setMessage('');
    const body = JSON.stringify(payload);
    const signature = `${path}:${method}:${body}`;
    if (receipt.current?.signature !== signature)
      receipt.current = { signature, key: crypto.randomUUID() };
    try {
      const value = await request<Workflow>(path, {
        method,
        body,
        headers: {
          'Content-Type': 'application/json',
          'X-GEOMG-Request': '1',
          'Idempotency-Key': receipt.current.key,
        },
      });
      receipt.current = null;
      adopt(value);
      setTitle('');
      setSelected(value.workflow_id);
      setRefresh((n) => n + 1);
      setMessage('Workflow saved. Activation does not start work.');
      onChanged();
      heading.current?.focus();
    } catch (failure) {
      setError(failure as Error);
    } finally {
      working(false);
    }
  }
  async function compare() {
    if (!item) return;
    working(true);
    try {
      setComparison(await request<Workflow>(`${base}/${item.workflow_id}`));
    } catch (failure) {
      setError(failure as Error);
    } finally {
      working(false);
    }
  }
  const locked = busy || disabled;
  const canEdit = !!item?.draft && item.can_change && !retired;
  return (
    <section
      className="mt-8 min-w-0 border-t border-border pt-6"
      aria-label="Workflows"
    >
      <h2 ref={heading} tabIndex={-1}>
        Workflows
      </h2>
      <ActionButton
        className={ui.secondary}
        disabled={dirty || locked}
        aria-expanded={open}
        aria-controls="workflow-details"
        onClick={() => {
          setOpen(!open);
          setError(null);
        }}
      >
        {' '}
        {open ? 'Hide Workflows' : 'Show Workflows'}
      </ActionButton>
      <p role="status">
        {busy
          ? 'Saving or loading Workflow…'
          : message || (dirty ? 'Unsaved Workflow changes' : '')}
      </p>
      {open && (
        <div
          id="workflow-details"
          className="mt-4 [&_h4]:mb-3 [&_h4]:font-semibold"
        >
          {error && (
            <div ref={errorBox} tabIndex={-1} role="alert" className={ui.error}>
              <p>{error.message}</p>
              {error instanceof ApiError && error.fields.length > 0 && (
                <ul>
                  {error.fields.map((f, i) => (
                    <li key={i}>
                      {f.field}: {f.message}
                    </li>
                  ))}
                </ul>
              )}
              {item && (
                <ActionButton
                  className={ui.secondary}
                  disabled={locked}
                  onClick={() => void compare()}
                >
                  Load saved Workflow for comparison
                </ActionButton>
              )}
              {(!contract || !page || !item) && (
                <ActionButton
                  className={ui.secondary}
                  onClick={() => {
                    setError(null);
                    setRefresh((n) => n + 1);
                    setReadRetry((n) => n + 1);
                  }}
                >
                  Retry Workflows
                </ActionButton>
              )}
            </div>
          )}
          {comparison && (
            <div className={ui.notice}>
              <h3>Saved Workflow version {comparison.lock_version}</h3>
              <DefinitionView version={comparison.draft ?? comparison.active} />
              <p>
                Your draft is preserved. Review these saved processes before
                replacing them with your changes.
              </p>
              {comparison.draft && comparison.can_change && (
                <ActionButton
                  className={ui.secondary}
                  disabled={locked}
                  onClick={() => {
                    adopt(comparison, true);
                    receipt.current = null;
                  }}
                >
                  Keep my draft against the latest version
                </ActionButton>
              )}
              <ActionButton
                className={ui.secondary}
                disabled={locked}
                onClick={() => {
                  adopt(comparison);
                  receipt.current = null;
                }}
              >
                Use saved Workflow and discard my changes
              </ActionButton>
            </div>
          )}
          {!contract || !page ? (
            !error && <p role="status">Loading Workflows…</p>
          ) : (
            <>
              <label className="mb-2 block" htmlFor="workflow-choice">
                Workflow
              </label>
              <SelectControl
                id="workflow-choice"
                value={selected}
                disabled={dirty || locked}
                onChange={(event) => {
                  setSelected(event.target.value);
                  setItem(null);
                  setError(null);
                  setDraft([]);
                  setBaseline('[]');
                }}
              >
                <option value="">Select a Workflow</option>
                {page.items.map((row) => (
                  <option key={row.workflow_id} value={row.workflow_id}>
                    {row.title}
                  </option>
                ))}
                {item &&
                  !page.items.some(
                    (row) => row.workflow_id === item.workflow_id
                  ) && <option value={item.workflow_id}>{item.title}</option>}
              </SelectControl>
              <p>{page.total} Workflows in this Set</p>
              {(page.total > page.limit || offset > 0) && (
                <div className={ui.pagination}>
                  <ActionButton
                    disabled={dirty || locked || offset === 0}
                    onClick={() => setOffset(Math.max(0, offset - page.limit))}
                  >
                    Previous Workflows
                  </ActionButton>
                  <ActionButton
                    disabled={
                      dirty || locked || offset + page.limit >= page.total
                    }
                    onClick={() => setOffset(offset + page.limit)}
                  >
                    Next Workflows
                  </ActionButton>
                </div>
              )}
              {!selected && contract.can_create && !retired && (
                <form
                  className={`${ui.form} grid gap-4 sm:grid-cols-2 [&>input]:col-span-full [&>label]:col-span-full`}
                  onSubmit={(event) => {
                    event.preventDefault();
                    void mutate(base, 'POST', {
                      set_id: setId,
                      title,
                      processes: [],
                    });
                  }}
                >
                  <label htmlFor="workflow-title">New Workflow title</label>
                  <TextInput
                    id="workflow-title"
                    required
                    value={title}
                    disabled={locked}
                    onChange={(event) => setTitle(event.target.value)}
                  />
                  <ActionButton
                    className={ui.primary}
                    disabled={locked || !title.trim()}
                  >
                    Create Workflow draft
                  </ActionButton>
                  {title && (
                    <ActionButton
                      type="button"
                      className={ui.secondary}
                      disabled={locked}
                      onClick={() => setTitle('')}
                    >
                      Discard new Workflow
                    </ActionButton>
                  )}
                </form>
              )}
              <details>
                <summary>Process types and definitions</summary>
                <dl className={ui.definitionList}>
                  {contract.process_types.map((type) => (
                    <div key={type.key}>
                      <dt>{type.label}</dt>
                      <dd>{type.definition}</dd>
                    </div>
                  ))}
                </dl>
              </details>
              {selected && !item && !error && (
                <p role="status">Loading Workflow definition…</p>
              )}
              {item && (
                <>
                  <h3>
                    {item.title} · version {item.lock_version}
                  </h3>
                  <h4>Active definition</h4>
                  <DefinitionView version={item.active} />
                  {item.can_change &&
                    !retired &&
                    item.active &&
                    !item.draft && (
                      <ActionButton
                        className={ui.secondary}
                        disabled={locked}
                        onClick={() =>
                          void mutate(
                            `${base}/${item.workflow_id}/draft`,
                            'POST',
                            { lock_version: item.lock_version }
                          )
                        }
                      >
                        Clone active version to draft
                      </ActionButton>
                    )}
                  {item.draft && (
                    <form
                      className={ui.form}
                      onSubmit={(event) => {
                        event.preventDefault();
                        void mutate(
                          `${base}/${item.workflow_id}/draft`,
                          'PUT',
                          {
                            lock_version: item.lock_version,
                            processes: wire(draft),
                          }
                        );
                      }}
                    >
                      <h4>Draft definition {item.draft.number}</h4>
                      <p>
                        Configuration references name managed settings. Never
                        enter credential values. Activation makes a definition
                        current; execution is separate.
                      </p>
                      <fieldset disabled={!canEdit || locked}>
                        <legend>Ordered processes</legend>
                        {draft.map((process, index) => {
                          const type = contract.process_types.find(
                            (t) => t.key === process.process_type
                          )!;
                          function change(patch: Partial<Editable>) {
                            edit(
                              draft.map((p, i) =>
                                i === index ? { ...p, ...patch } : p
                              )
                            );
                          }
                          function move(delta: number) {
                            const next = [...draft];
                            [next[index], next[index + delta]] = [
                              next[index + delta],
                              next[index],
                            ];
                            edit(next);
                            setMessage(
                              `Process moved to position ${index + delta + 1}.`
                            );
                          }
                          return (
                            <div
                              className="my-4 grid gap-3 rounded-lg border border-border bg-surface-subtle p-4 [&_p]:mb-0"
                              key={process.localId}
                            >
                              <label htmlFor={`${process.localId}-type`}>
                                Process {index + 1} type
                              </label>
                              <SelectControl
                                id={`${process.localId}-type`}
                                value={process.process_type}
                                onChange={(event) =>
                                  change({
                                    process_type: event.target.value,
                                    configuration: {},
                                  })
                                }
                              >
                                {contract.process_types.map((t) => (
                                  <option key={t.key} value={t.key}>
                                    {t.label}
                                  </option>
                                ))}
                              </SelectControl>
                              <p>{type.definition}</p>
                              <label htmlFor={`${process.localId}-name`}>
                                Process {index + 1} name
                              </label>
                              <TextInput
                                id={`${process.localId}-name`}
                                required
                                value={process.name}
                                onChange={(event) =>
                                  change({ name: event.target.value })
                                }
                              />
                              {type.configuration_fields.map((field) => (
                                <div className={ui.field} key={field}>
                                  <label
                                    htmlFor={`${process.localId}-${field}`}
                                  >
                                    {
                                      contract.configuration_schema.properties[
                                        field
                                      ].title
                                    }{' '}
                                    for process {index + 1}
                                  </label>
                                  <TextInput
                                    id={`${process.localId}-${field}`}
                                    value={process.configuration[field] ?? ''}
                                    onChange={(event) =>
                                      change({
                                        configuration: {
                                          ...process.configuration,
                                          [field]: event.target.value || null,
                                        },
                                      })
                                    }
                                  />
                                </div>
                              ))}
                              <div className={ui.actions}>
                                <ActionButton
                                  type="button"
                                  aria-label={`Move process ${index + 1} up`}
                                  disabled={index === 0}
                                  onClick={() => move(-1)}
                                >
                                  Move up
                                </ActionButton>
                                <ActionButton
                                  type="button"
                                  aria-label={`Move process ${index + 1} down`}
                                  disabled={index === draft.length - 1}
                                  onClick={() => move(1)}
                                >
                                  Move down
                                </ActionButton>
                                <ActionButton
                                  type="button"
                                  aria-label={`Remove process ${index + 1}`}
                                  onClick={() =>
                                    edit(draft.filter((_, i) => i !== index))
                                  }
                                >
                                  Remove
                                </ActionButton>
                              </div>
                            </div>
                          );
                        })}
                        <ActionButton
                          type="button"
                          disabled={draft.length >= contract.maximum_processes}
                          onClick={() =>
                            edit([
                              ...draft,
                              ...editable([
                                {
                                  position: draft.length + 1,
                                  process_type: contract.process_types[0].key,
                                  name: contract.process_types[0].label,
                                  configuration_schema_version:
                                    contract.configuration_schema_version,
                                  configuration: {},
                                },
                              ]),
                            ])
                          }
                        >
                          Add process
                        </ActionButton>
                      </fieldset>
                      {canEdit && (
                        <div className={ui.actions}>
                          <ActionButton
                            className={ui.primary}
                            disabled={
                              locked ||
                              !dirty ||
                              !!comparison ||
                              (error instanceof ApiError &&
                                error.code === 'stale_version')
                            }
                          >
                            Save Workflow draft
                          </ActionButton>
                          <ActionButton
                            type="button"
                            className={ui.secondary}
                            disabled={locked || !dirty}
                            onClick={() => adopt(item)}
                          >
                            Discard Workflow edits
                          </ActionButton>
                        </div>
                      )}
                    </form>
                  )}
                  {item.draft && item.can_activate && !retired && (
                    <div>
                      <p>
                        Activating draft {item.draft.number} supersedes the
                        current active definition. Existing executions must
                        retain their pinned version.
                      </p>
                      <label>
                        <TextInput
                          type="checkbox"
                          checked={confirmed}
                          disabled={dirty || locked}
                          onChange={(event) =>
                            setConfirmed(event.target.checked)
                          }
                        />{' '}
                        I reviewed the saved draft and confirm activation.
                      </label>
                      <ActionButton
                        className={ui.primary}
                        disabled={dirty || locked || !confirmed || !!comparison}
                        onClick={() =>
                          void mutate(
                            `${base}/${item.workflow_id}/activate`,
                            'POST',
                            {
                              lock_version: item.lock_version,
                              version_id: item.draft!.version_id,
                              confirmed: true,
                            }
                          )
                        }
                      >
                        Activate saved draft
                      </ActionButton>
                    </div>
                  )}
                  <History
                    key={`${item.workflow_id}:${item.lock_version}`}
                    workflowId={item.workflow_id}
                  />
                </>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

function DefinitionView({ version }: { version: Version | null }) {
  return version ? (
    <div>
      <p>
        Version {version.number} · {version.state}
      </p>
      {version.checksum && <small>Checksum: {version.checksum}</small>}
      <ol>
        {version.processes.map((p) => (
          <li key={p.position}>
            <strong>{p.name}</strong> · {p.process_type}
            <dl>
              {Object.entries(p.configuration)
                .filter(([, value]) => value !== null)
                .map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
            </dl>
          </li>
        ))}
      </ol>
    </div>
  ) : (
    <p>No active definition.</p>
  );
}
function History({ workflowId }: { workflowId: string }) {
  const [page, setPage] = useState<Page<Version> | null>(null);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  useEffect(
    () => () => {
      generation.current += 1;
    },
    []
  );
  async function load(next: number) {
    const current = ++generation.current;
    setError('');
    setLoading(true);
    try {
      const result = await request<Page<Version>>(
        `${base}/${workflowId}/versions?offset=${next}&limit=5`
      );
      if (current === generation.current) {
        setPage(result);
        setOffset(next);
      }
    } catch (failure) {
      if (current === generation.current) setError((failure as Error).message);
    } finally {
      if (current === generation.current) setLoading(false);
    }
  }
  return (
    <div>
      <ActionButton
        className={ui.secondary}
        disabled={loading}
        onClick={() => void load(offset)}
      >
        {page ? 'Refresh version history' : 'Show version history'}
      </ActionButton>
      {loading && <p role="status">Loading version history…</p>}
      {error && <p role="alert">{error}</p>}
      {page && (
        <>
          <h4>Version history</h4>
          {page.items.map((version) => (
            <details key={version.version_id}>
              <summary>
                Version {version.number} · {version.state}
              </summary>
              <DefinitionView version={version} />
            </details>
          ))}
          <ActionButton
            disabled={loading || offset === 0}
            onClick={() => void load(Math.max(0, offset - page.limit))}
          >
            Newer versions
          </ActionButton>
          <ActionButton
            disabled={loading || offset + page.limit >= page.total}
            onClick={() => void load(offset + page.limit)}
          >
            Older versions
          </ActionButton>
        </>
      )}
    </div>
  );
}
