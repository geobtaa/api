import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { request, type Page } from '../api';
import { Load, Pages } from '../sources/SourceBrowse';
import { ActionButton, DataTable, SelectControl } from '../ui/controls';
import { ui } from '../ui/styles';
import { resourcePath } from '../urlIds';
import { DraftBoundary } from '../work/DraftBoundary';
import { useCommand } from '../work/useCommand';
import { FieldControl, type Field } from './ResourceEditor';

const base = '/api/v1/admin/resource-bulk-actions';
const historyPath = '/resource-bulk-actions';
const pageSize = 25;
type Summary = {
  id: string;
  selection_id: string;
  reverts: string | null;
  created_at: string;
  actor_name: string;
  applied_at: string | null;
  applied_by: string | null;
  field_labels: Record<string, string>;
};
type Item = {
  resource_id: string;
  before_version: number;
  after_version: number | null;
  status: string;
  changes: Record<string, { before: unknown; after: unknown }>;
};
type Detail = Page<Item> & Summary & { totals: Record<string, number> };
const statuses: Record<string, string> = {
  ready: 'Ready',
  changed: 'Changed',
  unchanged: 'Unchanged',
  conflict: 'Version or Set changed',
  read_only: 'Read-only',
  active_job: 'Active job',
};
function display(value: unknown): string {
  if (value === null) return 'Not supplied';
  if (Array.isArray(value))
    return value.length ? JSON.stringify(value) : 'Empty list';
  return value === '' ? 'Empty text' : String(value);
}
function Heading({ children }: { children: string }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), [children]);
  return (
    <h1 ref={heading} tabIndex={-1}>
      {children}
    </h1>
  );
}

export function BulkEditPage() {
  const { selectionId } = useParams();
  return (
    <main className={ui.page} id="main-content">
      <Link className={ui.backLink} to={`/resources/selections/${selectionId}`}>
        ← Saved selection
      </Link>
      <Heading>Bulk edit Resources</Heading>
      <Load<{
        fields: Field[];
        can_bulk_edit: boolean;
      }> url="/api/v1/admin/contracts/resources">
        {(contract) =>
          contract.can_bulk_edit ? (
            <DraftBoundary>
              <EditForm
                key={selectionId}
                id={selectionId!}
                fields={contract.fields}
              />
            </DraftBoundary>
          ) : (
            <p className={ui.notice}>Bulk edit permission is required.</p>
          )
        }
      </Load>
    </main>
  );
}

type Replacement = { value: unknown; clear: boolean };
function EditForm({ id, fields }: { id: string; fields: Field[] }) {
  const command = useCommand();
  const navigate = useNavigate();
  const [edits, setEdits] = useState<Record<string, Replacement>>({});
  const remaining = fields.filter((field) => !(field.name in edits));
  function change(name: string, patch: Replacement) {
    command.formProps.onChange();
    setEdits((current) => ({ ...current, [name]: patch }));
  }
  async function preview(event: FormEvent) {
    event.preventDefault();
    const values: Record<string, unknown> = {};
    const clear_fields: string[] = [];
    for (const [name, edit] of Object.entries(edits)) {
      if (edit.clear) clear_fields.push(name);
      else values[name] = edit.value;
    }
    try {
      const result = await command.run<{ id: string }>(base, 'POST', {
        selection_id: id,
        values,
        clear_fields,
      });
      navigate(`${historyPath}/${result.id}`);
    } catch {
      /* Keep proposed values and the retry key. */
    }
  }
  return (
    <form
      className={`${ui.form} max-w-4xl`}
      onSubmit={preview}
      onReset={() => {
        setEdits({});
        command.formProps.onReset();
      }}
    >
      <fieldset disabled={command.busy}>
        <p>
          Replace the selected fields on every editable draft in this saved
          result set. A replacement list supplies all values for that field.
        </p>
        {Object.entries(edits).map(([name, edit]) => {
          const field = fields.find((f) => f.name === name)!;
          return (
            <fieldset
              key={name}
              className="mb-4 rounded-md border border-border p-4"
            >
              <legend className="px-1 font-semibold">{field.label}</legend>
              {!edit.clear && (
                <>
                  <label
                    className={ui.field}
                    htmlFor={`resource-field-${name}`}
                  >
                    {field.kind.includes('list') &&
                    !(Array.isArray(edit.value) && edit.value.length)
                      ? 'Add'
                      : 'New'}{' '}
                    {field.label.toLowerCase()}
                  </label>
                  <FieldControl
                    field={field}
                    value={edit.value}
                    change={(value) => change(name, { ...edit, value })}
                  />
                </>
              )}
              <div className="mt-2 flex items-center gap-4">
                {!field.required && (
                  <label className={ui.checkbox}>
                    <input
                      className="form-checkbox"
                      type="checkbox"
                      checked={edit.clear}
                      onChange={(e) =>
                        change(name, { ...edit, clear: e.target.checked })
                      }
                    />
                    Clear {field.label.toLowerCase()}
                  </label>
                )}
                <ActionButton
                  type="button"
                  className={ui.textAction}
                  onClick={() => {
                    const next = { ...edits };
                    delete next[name];
                    setEdits(next);
                    command.formProps.onChange();
                  }}
                >
                  Remove {field.label.toLowerCase()} from edit
                </ActionButton>
              </div>
            </fieldset>
          );
        })}
        {remaining.length > 0 && (
          <label className={ui.field}>
            Add a field
            <SelectControl
              value=""
              onChange={(e) => {
                change(e.target.value, { clear: false, value: undefined });
              }}
            >
              <option value="" disabled>
                Choose a field
              </option>
              {remaining.map((field) => (
                <option key={field.name} value={field.name}>
                  {field.label}
                </option>
              ))}
            </SelectControl>
          </label>
        )}
        <div className={ui.actions}>
          <ActionButton
            className={ui.primary}
            type="submit"
            disabled={
              !Object.keys(edits).length ||
              Object.values(edits).some(
                (edit) => !edit.clear && edit.value === undefined
              )
            }
          >
            Preview changes
          </ActionButton>
          {command.feedback}
        </div>
      </fieldset>
    </form>
  );
}

export function BulkHistoryPage() {
  const [offset, setOffset] = useState(0);
  return (
    <main id="main-content" className={ui.page}>
      <Link to="/resources" className={ui.backLink}>
        ← Resources
      </Link>
      <Heading>My bulk actions</Heading>
      <Load<Page<Summary>> url={`${base}?offset=${offset}&limit=${pageSize}`}>
        {(page) => (
          <>
            {page.total === 0 ? (
              <p>No bulk actions yet.</p>
            ) : (
              <DataTable>
                <caption className="sr-only">Bulk action history</caption>
                <thead>
                  <tr>
                    <th>Action</th>
                    <th>Fields</th>
                    <th>Staff</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((action) => (
                    <tr key={action.id}>
                      <th scope="row">
                        <Link to={`${historyPath}/${action.id}`}>
                          {action.reverts ? 'Revert' : 'Edit'} ·{' '}
                          {new Date(
                            action.applied_at ?? action.created_at
                          ).toLocaleString()}
                        </Link>
                      </th>
                      <td>{Object.values(action.field_labels).join(', ')}</td>
                      <td>{action.applied_by ?? action.actor_name}</td>
                      <td>{action.applied_at ? 'Confirmed' : 'Preview'}</td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            )}
            <Pages
              label="Bulk action history pages"
              page={page}
              change={setOffset}
            />
          </>
        )}
      </Load>
    </main>
  );
}

export function BulkReviewPage() {
  const { actionId } = useParams();
  return <Review key={actionId} id={actionId!} />;
}
function Review({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={historyPath}>
        ← My bulk actions
      </Link>
      <Load<Detail>
        key={revision}
        url={`${base}/${id}?offset=${offset}&limit=${pageSize}`}
      >
        {(data) => (
          <>
            <Heading>
              {data.applied_at
                ? 'Bulk action results'
                : data.reverts
                  ? 'Preview revert'
                  : 'Preview bulk edit'}
            </Heading>
            <p>
              {data.applied_at ? 'Confirmed' : 'Prepared'} by{' '}
              {data.applied_by ?? data.actor_name} ·{' '}
              {new Date(data.applied_at ?? data.created_at).toLocaleString()}
            </p>
            <p>Fields: {Object.values(data.field_labels).join(', ')}</p>
            <Link to={`/resources/selections/${data.selection_id}`}>
              View saved selection
            </Link>
            {data.reverts && (
              <Link to={`${historyPath}/${data.reverts}`}>
                View original edit
              </Link>
            )}
            <p role="status">
              {data.total} Resources ·{' '}
              {Object.entries(data.totals)
                .map(([state, count]) => `${statuses[state]}: ${count}`)
                .join(' · ')}
            </p>
            {!data.applied_at && (
              <p>
                Confirmation updates only Resources marked Ready that still have
                the reviewed version and remain editable.
              </p>
            )}
            <ActionControls
              data={data}
              refresh={() => setRevision((v) => v + 1)}
            />
            <div className={ui.tableRegion}>
              <DataTable>
                <caption className="sr-only">
                  Per-Resource versions and proposed field changes
                </caption>
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>Version</th>
                    <th>Outcome</th>
                    <th>Field changes</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr key={row.resource_id}>
                      <th scope="row">
                        <Link to={resourcePath(row.resource_id)}>
                          {row.resource_id}
                        </Link>
                      </th>
                      <td>
                        {row.before_version}
                        {row.after_version !== null &&
                          ` → ${row.after_version}`}
                      </td>
                      <td>{statuses[row.status]}</td>
                      <td>
                        {Object.entries(row.changes).map(([name, c]) => (
                          <div key={name} className="mb-2 break-words">
                            <strong>{data.field_labels[name]}</strong>
                            <div>Before: {display(c.before)}</div>
                            <div>
                              {row.status === 'changed' ? 'After' : 'Proposed'}:{' '}
                              {display(c.after)}
                            </div>
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            </div>
            <Pages label="Bulk action records" page={data} change={setOffset} />
          </>
        )}
      </Load>
    </main>
  );
}
function ActionControls({
  data,
  refresh,
}: {
  data: Detail;
  refresh: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const alert = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    if (error) alert.current?.focus();
  }, [error]);
  const key = useRef<string | null>(null);
  const navigate = useNavigate();
  const undo = Boolean(data.applied_at);
  async function run() {
    setBusy(true);
    setError('');
    key.current ??= crypto.randomUUID();
    try {
      const result = await request<{ id: string }>(
        `${base}/${data.id}/${undo ? 'reversions' : 'confirmation'}`,
        {
          method: undo ? 'POST' : 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-GEOMG-Request': '1',
            'Idempotency-Key': key.current,
          },
          ...(undo ? {} : { body: JSON.stringify({ confirmed: true }) }),
        }
      );
      if (undo) navigate(`${historyPath}/${result.id}`);
      else refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  if (undo ? data.reverts || !data.totals.changed : !data.totals.ready)
    return null;
  return (
    <div className="my-4">
      <ActionButton
        type="button"
        className={ui.primary}
        disabled={busy}
        onClick={() => void run()}
      >
        {undo
          ? 'Preview revert'
          : data.reverts
            ? `Confirm revert for ${data.totals.ready} Resources`
            : `Confirm changes to ${data.totals.ready} Resources`}
      </ActionButton>
      {error && (
        <p role="alert" tabIndex={-1} ref={alert} className={ui.error}>
          {error}
        </p>
      )}
    </div>
  );
}
