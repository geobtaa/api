import { resourceApiPath } from '../urlIds';
import { ui } from '../ui/styles';
import {
  TextInput,
  TextArea,
  SelectControl,
  ActionButton,
} from '../ui/controls';
import { useEffect, useRef, useState } from 'react';
import { Link, useBeforeUnload, useBlocker } from 'react-router';
import { ApiError, request } from '../sets/api';
import { DiscardDialog } from '../ui/DiscardDialog';
import { type Resource } from './ResourcePages';
import { ResourceRelationships } from './ResourceRelationships';

export type Distribution = {
  distribution_type_id: number;
  url: string;
  label: string | null;
};
export type ResourceDetailData = Resource & {
  editable?: boolean;
  projection_status?: 'pending' | 'live' | null;
  distributions?: Distribution[];
  source_record: Record<string, unknown> | null;
  import_warnings: string[];
};
export type Field = {
  name: string;
  label: string;
  section: string;
  kind: string;
  required: boolean;
  choices: string[];
  multiline: boolean;
};
type Contract = {
  fields: Field[];
  sections: string[];
  distribution_types: { id: number; distribution_type: string }[];
  can_update: boolean;
  maximum_values: number;
};

export function ResourceEditor({
  item,
  onSaved,
}: {
  item: ResourceDetailData;
  onSaved: (value: ResourceDetailData) => void;
}) {
  const [contract, setContract] = useState<Contract | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    request<Contract>('/api/v1/admin/contracts/resources')
      .then((value) => {
        if (!Array.isArray(value.fields))
          throw new Error('Invalid editor contract');
        if (active) setContract(value);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [retry]);
  if (failed)
    return (
      <div role="alert" className={ui.notice}>
        <p>The editor could not be loaded.</p>
        <ActionButton
          className={ui.secondary}
          onClick={() => {
            setFailed(false);
            setRetry(retry + 1);
          }}
        >
          Retry editor
        </ActionButton>
      </div>
    );
  if (!contract) return <p role="status">Loading editor…</p>;
  return <EditorForm item={item} contract={contract} onSaved={onSaved} />;
}

function EditorForm({
  item,
  contract,
  onSaved,
}: {
  item: ResourceDetailData;
  contract: Contract;
  onSaved: (value: ResourceDetailData) => void;
}) {
  const sections = contract.sections;
  const [section, setSection] = useState(sections[0]);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [clears, setClears] = useState<string[]>([]);
  const [links, setLinks] = useState<Distribution[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState('');
  const [latest, setLatest] = useState<ResourceDetailData | null>(null);
  const [base, setBase] = useState(item);
  const [preview, setPreview] = useState<{
    body: string;
    preview_id: string;
    changes: Record<string, { before: unknown; after: unknown }>;
  } | null>(null);
  const published = base.publication_state === 'published';
  useEffect(() => {
    if (base.projection_status !== 'pending') return;
    let active = true;
    const timer = window.setInterval(async () => {
      try {
        const current = await request<ResourceDetailData>(
          resourceApiPath(item.id)
        );
        if (
          active &&
          current.lock_version === base.lock_version &&
          current.projection_status === 'live'
        ) {
          setBase(current);
          setSaved('Live on dev2');
        }
      } catch {
        /* Retain the saved status and retry the read. */
      }
    }, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [base.lock_version, base.projection_status, item.id]);
  const receipt = useRef<{ body: string; key: string } | null>(null);
  const summary = useRef<HTMLDivElement>(null);
  const dirty =
    Object.keys(values).length > 0 || clears.length > 0 || links !== null;
  const editable = contract.can_update && !!base.editable;
  const blocker = useBlocker(dirty || busy);
  useBeforeUnload((event) => {
    if (dirty || busy) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  useEffect(() => {
    if (error) summary.current?.focus();
  }, [error]);
  useEffect(() => {
    if (!dirty && !busy && blocker.state === 'blocked') blocker.proceed();
  }, [dirty, busy, blocker]);
  function change(name: string, value: unknown) {
    setPreview(null);
    setSaved('');
    setClears((old) => old.filter((field) => field !== name));
    setValues((old) => {
      const next = { ...old };
      if (JSON.stringify(value) === JSON.stringify(base.metadata[name]))
        delete next[name];
      else next[name] = value;
      return next;
    });
  }
  function clear(name: string) {
    setPreview(null);
    setSaved('');
    setValues((old) => {
      const next = { ...old };
      delete next[name];
      return next;
    });
    setClears((old) =>
      old.includes(name)
        ? old.filter((field) => field !== name)
        : [...old, name]
    );
  }
  function changeLinks(next: Distribution[]) {
    setPreview(null);
    setSaved('');
    setLinks(
      JSON.stringify(next) === JSON.stringify(base.distributions ?? [])
        ? null
        : next
    );
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!editable) return;
    setBusy(true);
    setError(null);
    setSaved('');
    const body = JSON.stringify({
      lock_version: base.lock_version,
      values,
      clear_fields: clears,
      ...(links !== null ? { distributions: links } : {}),
    });
    if (receipt.current?.body !== body)
      receipt.current = { body, key: crypto.randomUUID() };
    try {
      const path = resourceApiPath(item.id);
      if (published && preview?.body !== body) {
        const result = await request<{
          preview_id: string;
          changes: Record<string, { before: unknown; after: unknown }>;
        }>(path + '/published-edits/preview', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-GEOMG-Request': '1',
          },
          body,
        });
        setPreview({ ...result, body });
        return;
      }
      const result = await request<ResourceDetailData>(
        published ? path + '/published-edits' : path,
        {
          method: published ? 'POST' : 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'X-GEOMG-Request': '1',
            'Idempotency-Key': receipt.current.key,
          },
          body: published
            ? JSON.stringify({
                confirmed: true,
                preview_id: preview?.preview_id,
                edit: JSON.parse(body),
              })
            : body,
        }
      );
      setBase(result);
      onSaved(result);
      setValues({});
      setClears([]);
      setLinks(null);
      setLatest(null);
      setPreview(null);
      setSaved(
        published
          ? result.projection_status === 'live'
            ? 'Live on dev2'
            : 'Saved · updating dev2'
          : `Saved version ${result.lock_version}.`
      );
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught
          : new ApiError('Could not save. Your draft is preserved.')
      );
    } finally {
      setBusy(false);
    }
  }
  async function loadLatest() {
    setBusy(true);
    try {
      setLatest(await request<ResourceDetailData>(resourceApiPath(item.id)));
    } catch {
      setError(
        new ApiError(
          'Latest version could not be loaded. Your draft is preserved.'
        )
      );
    } finally {
      setBusy(false);
    }
  }
  function adoptLatest(keepDraft: boolean) {
    if (!latest) return;
    setBase(latest);
    onSaved(latest);
    if (!keepDraft) {
      setValues({});
      setClears([]);
      setLinks(null);
    }
    setLatest(null);
    setError(null);
    receipt.current = null;
  }
  return (
    <section
      className="my-6 min-w-0 rounded-lg border border-border bg-surface shadow-xs"
      aria-label="Compact Resource editor"
    >
      {!editable && (
        <p className={ui.notice}>
          Read-only metadata. Editing requires update permission and a draft in
          a non-retired Set.
        </p>
      )}
      {error && (
        <div className={ui.error} role="alert" ref={summary} tabIndex={-1}>
          <h2>Changes need attention</h2>
          <p>
            {error.fields.length
              ? 'Review these validation errors. Your changes have not been saved.'
              : error.message}
          </p>
          {!!error.fields.length && (
            <ul>
              {error.fields.map((issue, index) => (
                <li key={index}>
                  {issue.field}: {issue.message}
                </li>
              ))}
            </ul>
          )}
          {error.code === 'stale_version' && (
            <ActionButton
              className={ui.secondary}
              disabled={busy}
              onClick={loadLatest}
            >
              Load latest for comparison
            </ActionButton>
          )}
        </div>
      )}
      {latest && (
        <div className={ui.notice}>
          <h2>Review saved version {latest.lock_version}</h2>
          <p>
            Your unsaved fields remain in the form. Compare each changed field
            before applying them to this version.
          </p>
          <dl className={ui.comparison}>
            {[...new Set([...Object.keys(values), ...clears])].map((name) => (
              <div key={name}>
                <dt>
                  {contract.fields.find((field) => field.name === name)
                    ?.label ?? name}
                </dt>
                <dd>
                  Saved: {JSON.stringify(latest.metadata[name] ?? null)}
                  <br />
                  Your draft:{' '}
                  {clears.includes(name)
                    ? 'Explicit clear'
                    : JSON.stringify(values[name])}
                </dd>
              </div>
            ))}
          </dl>
          {links !== null && (
            <>
              <h3>Saved Distributions</h3>
              <pre className="max-w-xl whitespace-pre-wrap text-xs [overflow-wrap:anywhere]">
                {JSON.stringify(latest.distributions, null, 2)}
              </pre>
              <h3>Your Distributions</h3>
              <pre className="max-w-xl whitespace-pre-wrap text-xs [overflow-wrap:anywhere]">
                {JSON.stringify(links, null, 2)}
              </pre>
            </>
          )}
          <div className={ui.actions}>
            <ActionButton
              className={ui.secondary}
              onClick={() => adoptLatest(true)}
            >
              Keep my changes on latest version
            </ActionButton>
            <ActionButton
              className={ui.secondary}
              onClick={() => adoptLatest(false)}
            >
              Discard my changes and use latest
            </ActionButton>
          </div>
        </div>
      )}
      <div
        className="flex gap-1 overflow-x-auto border-b border-border px-3 pt-2"
        role="tablist"
        aria-label="Resource metadata sections"
      >
        {sections.map((name, index) => (
          <ActionButton
            key={name}
            className="shrink-0 rounded-t-md border-b-2 border-transparent px-3 py-3 text-sm font-semibold text-text-secondary hover:bg-surface-subtle aria-selected:border-active aria-selected:bg-active-soft aria-selected:text-primary"
            id={`resource-tab-${index}`}
            role="tab"
            aria-selected={section === name}
            aria-controls={`resource-panel-${index}`}
            tabIndex={section === name ? 0 : -1}
            onClick={() => setSection(name)}
            onKeyDown={(event) => {
              const current = sections.indexOf(section);
              const next =
                event.key === 'ArrowRight'
                  ? (current + 1) % sections.length
                  : event.key === 'ArrowLeft'
                    ? (current - 1 + sections.length) % sections.length
                    : event.key === 'Home'
                      ? 0
                      : event.key === 'End'
                        ? sections.length - 1
                        : null;
              if (next !== null) {
                event.preventDefault();
                setSection(sections[next]);
                document.getElementById(`resource-tab-${next}`)?.focus();
              }
            }}
          >
            {name}
          </ActionButton>
        ))}
      </div>
      <form onSubmit={save} noValidate>
        {base.set_id && (
          <p className="px-4 py-3 text-sm">
            Source:{' '}
            <Link to={`/sources/${base.source_id}`}>{base.source_id}</Link>
            {' · '}Inherited from managing Set{' '}
            <Link to={`/sets/${base.set_id}`}>{base.set_title}</Link>.
          </p>
        )}
        <div
          role="tabpanel"
          id={`resource-panel-${sections.indexOf(section)}`}
          aria-labelledby={`resource-tab-${sections.indexOf(section)}`}
          tabIndex={0}
        >
          {section === 'Relationships' && (
            <ResourceRelationships
              key={`${base.id}:${base.lock_version}`}
              id={base.id}
            />
          )}
          <fieldset
            disabled={!editable || busy}
            className="min-w-0 p-4 [&_input:not([type=checkbox])]:h-10 [&_select]:h-10 [&_textarea]:h-24 [&_textarea]:min-h-24"
          >
            <legend className="sr-only">Descriptive metadata</legend>
            {section === 'Distributions' ? (
              <DistributionFields
                links={links ?? base.distributions ?? []}
                types={contract.distribution_types}
                maximum={contract.maximum_values}
                change={changeLinks}
              />
            ) : (
              <div className="grid grid-cols-1 items-start gap-x-5 gap-y-4 md:grid-cols-2">
                {contract.fields
                  .filter((field) => field.section === section)
                  .map((field) => (
                    <div
                      key={field.name}
                      className={`min-w-0 ${field.multiline ? 'md:col-span-2' : ''}`}
                    >
                      <div className="mb-1 flex min-h-6 items-center justify-between gap-2">
                        <label
                          className="text-sm font-medium leading-5"
                          title={field.name}
                          htmlFor={`resource-field-${field.name}`}
                        >
                          {field.label}
                          {field.required ? ' (required)' : ''}
                        </label>
                        {!field.required && (
                          <ActionButton
                            type="button"
                            className="shrink-0 rounded px-1 py-0.5 text-xs text-text-muted hover:bg-surface-muted hover:text-active"
                            aria-label={`${clears.includes(field.name) ? 'Undo clear for' : 'Clear'} ${field.label}`}
                            onClick={() => clear(field.name)}
                          >
                            {clears.includes(field.name)
                              ? 'Undo clear'
                              : 'Clear'}
                          </ActionButton>
                        )}
                      </div>
                      {clears.includes(field.name) ? (
                        <p className="rounded-md bg-active-soft p-3 text-sm text-primary">
                          This field will be cleared.
                        </p>
                      ) : (
                        <FieldControl
                          field={field}
                          value={
                            Object.hasOwn(values, field.name)
                              ? values[field.name]
                              : base.metadata[field.name]
                          }
                          change={(value) => change(field.name, value)}
                        />
                      )}
                    </div>
                  ))}
              </div>
            )}
          </fieldset>
        </div>
        <div className="sticky bottom-0 z-20 flex flex-wrap items-center justify-between gap-3 rounded-b-lg border-t border-border bg-surface px-4 py-2 [&_p]:mb-0 [&_p]:text-sm">
          <p role="status">
            {busy
              ? 'Saving…'
              : saved ||
                (dirty
                  ? 'Unsaved changes'
                  : `Version ${base.lock_version} · No unsaved changes`)}
          </p>
          {preview && (
            <section aria-label="Published edit preview">
              <h3>Review public changes</h3>
              <dl>
                {Object.entries(preview.changes).map(([field, change]) => (
                  <div key={field}>
                    <dt>{field}</dt>
                    <dd>Before: {JSON.stringify(change.before)}</dd>
                    <dd>After: {JSON.stringify(change.after)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          {editable && (
            <ActionButton
              type="submit"
              className={ui.primary}
              disabled={busy || !dirty || !!latest}
            >
              {published
                ? preview
                  ? busy
                    ? 'Saving published changes…'
                    : 'Confirm published changes'
                  : 'Preview published changes'
                : 'Save changes'}
            </ActionButton>
          )}
        </div>
      </form>
      {blocker.state === 'blocked' && (
        <DiscardDialog
          busy={busy}
          keep={() => blocker.reset()}
          discard={() => blocker.proceed()}
        />
      )}
    </section>
  );
}

export function FieldControl({
  field,
  value,
  change,
}: {
  field: Field;
  value: unknown;
  change: (value: unknown) => void;
}) {
  const id = `resource-field-${field.name}`;
  if (field.kind === 'list' || field.kind === 'integer_list') {
    const items = Array.isArray(value) ? value : [];
    return (
      <div className="min-w-0">
        <div className="max-h-64 overflow-y-auto">
          {items.map((item, index) => (
            <div
              className="mb-1 flex items-start gap-1 [&>input]:flex-1 [&>textarea]:flex-1"
              key={index}
            >
              {field.multiline ? (
                <TextArea
                  id={index === 0 ? id : undefined}
                  aria-label={`${field.label} ${index + 1}`}
                  rows={2}
                  value={String(item)}
                  onChange={(event) =>
                    change(
                      items.map((old, i) =>
                        i === index ? event.target.value : old
                      )
                    )
                  }
                />
              ) : (
                <TextInput
                  id={index === 0 ? id : undefined}
                  aria-label={`${field.label} ${index + 1}`}
                  type={field.kind === 'integer_list' ? 'number' : 'text'}
                  value={String(item)}
                  onChange={(event) =>
                    change(
                      items.map((old, i) =>
                        i === index
                          ? field.kind === 'integer_list' &&
                            event.target.value !== ''
                            ? Number(event.target.value)
                            : event.target.value
                          : old
                      )
                    )
                  }
                />
              )}
              <ActionButton
                type="button"
                className="flex size-10 shrink-0 items-center justify-center rounded text-lg text-text-muted hover:bg-danger-soft hover:text-danger"
                title={`Remove ${field.label} ${index + 1}`}
                aria-label={`Remove ${field.label} ${index + 1}`}
                onClick={() => change(items.filter((_, i) => i !== index))}
              >
                ×
              </ActionButton>
            </div>
          ))}
        </div>
        <ActionButton
          id={items.length === 0 ? id : undefined}
          type="button"
          className={
            items.length
              ? 'rounded px-1 py-0.5 text-xs font-medium text-active hover:bg-active-soft'
              : 'h-10 w-full rounded-md border border-dashed border-control px-3 text-left text-sm text-text-muted hover:border-active hover:text-active'
          }
          onClick={() => change([...items, ''])}
        >
          Add {field.label.toLowerCase()}
        </ActionButton>
      </div>
    );
  }
  if (field.kind === 'boolean')
    return (
      <SelectControl
        id={id}
        value={value === undefined || value === null ? '' : String(value)}
        onChange={(event) => change(event.target.value === 'true')}
      >
        <option value="" disabled>
          Not supplied
        </option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </SelectControl>
    );
  if (field.choices.length)
    return (
      <SelectControl
        id={id}
        value={String(value ?? '')}
        onChange={(event) => change(event.target.value)}
      >
        <option value="" disabled>
          Choose a value
        </option>
        {value && !field.choices.includes(String(value)) ? (
          <option value={String(value)}>
            {String(value)} (imported legacy value)
          </option>
        ) : null}
        {field.choices.map((choice) => (
          <option key={choice}>{choice}</option>
        ))}
      </SelectControl>
    );
  return field.multiline ? (
    <TextArea
      id={id}
      rows={3}
      value={String(value ?? '')}
      onChange={(event) => change(event.target.value)}
    />
  ) : (
    <TextInput
      id={id}
      value={String(value ?? '')}
      onChange={(event) => change(event.target.value)}
    />
  );
}
function DistributionFields({
  links,
  types,
  maximum,
  change,
}: {
  links: Distribution[];
  types: Contract['distribution_types'];
  maximum: number;
  change: (value: Distribution[]) => void;
}) {
  const update = (index: number, patch: Partial<Distribution>) =>
    change(
      links.map((link, i) => (i === index ? { ...link, ...patch } : link))
    );
  return (
    <>
      <p>
        Ordered access links. URLs are stored without fetching remote services.
      </p>
      <div className="mb-4 grid gap-3">
        {links.map((link, index) => (
          <div
            className="grid grid-cols-1 items-end gap-3 border-b border-border pb-4 md:grid-cols-2 xl:grid-cols-[minmax(10rem,1fr)_minmax(14rem,2fr)_minmax(8rem,1fr)_auto] [&_label]:min-w-0 [&_input]:mt-1 [&_select]:mt-1"
            key={index}
          >
            <label>
              Type {index + 1}
              <SelectControl
                value={link.distribution_type_id}
                onChange={(event) =>
                  update(index, {
                    distribution_type_id: Number(event.target.value),
                  })
                }
              >
                {types.map((type) => (
                  <option key={type.id} value={type.id}>
                    {type.distribution_type}
                  </option>
                ))}
              </SelectControl>
            </label>
            <label>
              URL {index + 1}
              <TextInput
                type="url"
                value={link.url}
                onChange={(event) => update(index, { url: event.target.value })}
              />
            </label>
            <label>
              Label {index + 1}
              <TextInput
                value={link.label ?? ''}
                onChange={(event) =>
                  update(index, { label: event.target.value || null })
                }
              />
            </label>
            <div className="flex gap-2 [&_button]:rounded-md [&_button]:border [&_button]:border-border-strong [&_button]:bg-surface [&_button]:p-2 [&_button:hover]:bg-surface-muted">
              <ActionButton
                type="button"
                disabled={index === 0}
                aria-label={`Move Distribution ${index + 1} up`}
                onClick={() => {
                  const next = [...links];
                  [next[index - 1], next[index]] = [
                    next[index],
                    next[index - 1],
                  ];
                  change(next);
                }}
              >
                Up
              </ActionButton>
              <ActionButton
                type="button"
                aria-label={`Remove Distribution ${index + 1}`}
                onClick={() => change(links.filter((_, i) => i !== index))}
              >
                Remove
              </ActionButton>
            </div>
          </div>
        ))}
      </div>
      <ActionButton
        type="button"
        className={ui.secondary}
        disabled={links.length >= maximum}
        onClick={() =>
          change([
            ...links,
            { distribution_type_id: types[0].id, url: '', label: null },
          ])
        }
      >
        Add Distribution
      </ActionButton>
    </>
  );
}
