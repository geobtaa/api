import { AssigneeSelect } from './AssigneeSelect';
import { DraftBoundary } from './DraftBoundary';
import { useCommand } from './useCommand';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { Load } from '../sources/SourceBrowse';
import {
  ActionButton,
  SelectControl,
  TextArea,
  TextInput,
} from '../ui/controls';
import { ui } from '../ui/styles';
import { encodeId } from '../urlIds';
import {
  ApiError,
  request,
  taskBase,
  today,
  type Period,
  type Task,
  type TaskEvents,
  type WorkContract,
} from './api';

const string = (data: FormData, key: string) => String(data.get(key) ?? '');

export function NewTaskPage() {
  return (
    <DraftBoundary>
      <NewTaskPageContent />
    </DraftBoundary>
  );
}
function NewTaskPageContent() {
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to="/work">
        ← Work
      </Link>
      <h1>New Task</h1>
      <Load<WorkContract> url="/api/v1/admin/contracts/tasks">
        {(rights) =>
          rights.create ? (
            <NewTaskForm rights={rights} />
          ) : (
            <p className={ui.notice}>Task creation permission is required.</p>
          )
        }
      </Load>
    </main>
  );
}
function NewTaskForm({ rights }: { rights: WorkContract }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const command = useCommand();
  const [search, setSearch] = useState('');
  const [setId, setSetId] = useState(params.get('set_id') ?? '');
  const [setTitle, setSetTitle] = useState(params.get('set_id') ?? '');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const result = await command.run<Task>(taskBase, 'POST', {
        set_id: setId,
        title: string(data, 'title'),
        work_type: string(data, 'work_type'),
        description: string(data, 'description'),
        due_on: string(data, 'due_on'),
        planned_on: string(data, 'planned_on') || null,
        assignee_id: string(data, 'assignee_id') || null,
      });
      navigate(`/tasks/${result.task_id}`);
    } catch {
      /* Keep the form and receipt available for correction/retry. */
    }
  }
  return (
    <form
      {...command.formProps}
      onReset={() => {
        command.formProps.onReset();
        setSetId(params.get('set_id') ?? '');
        setSetTitle(params.get('set_id') ?? '');
        setSearch('');
      }}
      onSubmit={submit}
      className={`${ui.form} max-w-4xl`}
    >
      <fieldset disabled={command.busy} className="contents">
        {command.feedback}
        <fieldset className="mb-6">
          <legend className="mb-2 font-semibold">
            Managing Set (required)
          </legend>
          <p>
            {setId
              ? `Selected: ${setTitle}`
              : 'Choose the Set this work concerns.'}
          </p>
          <label className={ui.field}>
            Find a Set
            <TextInput
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <Load<{ items: { set_id: string; title: string }[]; total: number }>
            url={`/api/v1/admin/sets?q=${encodeURIComponent(search)}&limit=25`}
          >
            {(page) => (
              <div className="mt-2 max-h-56 overflow-y-auto rounded border border-border">
                <p className="px-3 text-xs">
                  {page.total} matches. Refine the search if needed.
                </p>
                {page.items.map((item) => (
                  <label
                    key={item.set_id}
                    className="flex items-center gap-3 border-t border-border px-3 py-2 text-sm"
                  >
                    <TextInput
                      type="radio"
                      name="set_choice"
                      checked={setId === item.set_id}
                      onChange={() => {
                        setSetId(item.set_id);
                        setSetTitle(item.title);
                      }}
                    />
                    {item.title}
                    <small>{item.set_id}</small>
                  </label>
                ))}
              </div>
            )}
          </Load>
        </fieldset>
        <div className={ui.fieldGrid}>
          <label className={ui.field}>
            Title (required)
            <TextInput name="title" required maxLength={250} />
          </label>
          <label className={ui.field}>
            Work type
            <SelectControl name="work_type">
              {rights.work_types.map((type) => (
                <option key={type}>{type}</option>
              ))}
            </SelectControl>
          </label>
          <label className={ui.field}>
            Due date (required)
            <TextInput
              name="due_on"
              type="date"
              required
              defaultValue={today()}
            />
          </label>
          <label className={ui.field}>
            Planned date
            <TextInput name="planned_on" type="date" />
          </label>
          <AssigneeSelect key={setId} setId={setId} />
          <label className={`${ui.field} md:col-span-2`}>
            Instructions
            <TextArea name="description" maxLength={5000} />
          </label>
        </div>
        <div className={ui.actions}>
          <ActionButton
            className={ui.primary}
            disabled={command.busy || !setId}
          >
            Create Task
          </ActionButton>
          <Link className={ui.secondary} to="/work">
            Cancel
          </Link>
        </div>
      </fieldset>
    </form>
  );
}

export function TaskPage() {
  return (
    <DraftBoundary>
      <TaskPageContent />
    </DraftBoundary>
  );
}
function TaskPageContent() {
  const { taskId } = useParams();
  const [revision, setRevision] = useState(0);
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to="/work">
        ← Work
      </Link>
      <Load<WorkContract> url="/api/v1/admin/contracts/tasks">
        {(rights) => (
          <Load<Task>
            key={`${taskId}:${revision}`}
            url={`${taskBase}/${taskId}`}
          >
            {(task) => (
              <TaskRecord
                task={task}
                rights={rights}
                changed={() => setRevision(revision + 1)}
              />
            )}
          </Load>
        )}
      </Load>
    </main>
  );
}
function TaskRecord({
  task,
  rights,
  changed,
}: {
  task: Task;
  rights: WorkContract;
  changed: () => void;
}) {
  const terminal = ['completed', 'cancelled'].includes(task.status);
  return (
    <>
      <div className={ui.toolbar}>
        <div>
          <p className={ui.kicker}>
            {task.work_type}
            {task.recurring ? ' · Recurring occurrence' : ''}
          </p>
          <h1>{task.title}</h1>
          <p>
            <Link to={`/sets/${encodeId(task.set_id)}`}>{task.set_title}</Link>{' '}
            · {task.source_title}
          </p>
        </div>
        <span className={ui.badge}>{task.status.replaceAll('_', ' ')}</span>
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-[3fr_2fr]">
        <section className={ui.panel} aria-label="Task details">
          <p className="whitespace-pre-wrap">{task.description}</p>
          <dl className={ui.definitionList}>
            <div>
              <dt>Due date</dt>
              <dd>{task.due_on}</dd>
            </div>
            <div>
              <dt>Planned date</dt>
              <dd>{task.planned_on ?? 'Not scheduled'}</dd>
            </div>
            <div>
              <dt>Assignee</dt>
              <dd>{task.assignee_name ?? 'Unassigned'}</dd>
            </div>
          </dl>
          {task.completed_at && (
            <section aria-label="Completion evidence">
              <h2>Completed work</h2>
              <p className="whitespace-pre-wrap">{task.completion_summary}</p>
              <dl className={ui.definitionList}>
                <div>
                  <dt>Completed (UTC)</dt>
                  <dd>
                    {task.completed_at} by {task.completed_by_name}
                  </dd>
                </div>
                <div>
                  <dt>Recorded (UTC)</dt>
                  <dd>{task.completion_recorded_at}</dd>
                </div>
                <div>
                  <dt>Resources</dt>
                  <dd>
                    {task.processed_count} processed · {task.changed_count}{' '}
                    changed
                  </dd>
                </div>
              </dl>
              <ul>
                {task.evidence.map((item, index) => (
                  <li key={index}>
                    <a
                      className="text-active underline"
                      href={item.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {!terminal && rights.update && (
            <details>
              <summary className="cursor-pointer py-3 font-semibold">
                Edit Task
              </summary>
              <EditTask task={task} rights={rights} changed={changed} />
            </details>
          )}
          {!terminal && rights.complete && (
            <details>
              <summary className="cursor-pointer py-3 font-semibold">
                Complete this occurrence
              </summary>
              <CompleteTask task={task} changed={changed} />
            </details>
          )}
          {task.predecessor_id && (
            <Link className={ui.backLink} to={`/tasks/${task.predecessor_id}`}>
              Previous occurrence
            </Link>
          )}
        </section>
        <section aria-label="Task activity" className={ui.panel}>
          <h2>Activity</h2>
          <TaskHistory taskId={task.task_id} />
        </section>
      </div>
    </>
  );
}

function EditTask({
  task,
  rights,
  changed,
}: {
  task: Task;
  rights: WorkContract;
  changed: () => void;
}) {
  const command = useCommand();
  const [version, setVersion] = useState(task.lock_version);
  const [conflict, setConflict] = useState(false);
  const [current, setCurrent] = useState<Task | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await command.run(`${taskBase}/${task.task_id}`, 'PATCH', {
        lock_version: version,
        title: string(data, 'title'),
        description: string(data, 'description'),
        due_on: string(data, 'due_on'),
        planned_on: string(data, 'planned_on') || null,
        assignee_id: string(data, 'assignee_id') || null,
        status: string(data, 'status'),
        reason: string(data, 'reason'),
      });
      changed();
    } catch (error) {
      if (error instanceof ApiError && error.code === 'stale_version')
        setConflict(true);
    }
  }
  async function reload() {
    try {
      const saved = await request<Task>(`${taskBase}/${task.task_id}`);
      setCurrent(saved);
      setVersion(saved.lock_version);
      setConflict(false);
    } catch {
      /* Original error remains visible. */
    }
  }
  return (
    <form {...command.formProps} onSubmit={submit}>
      <fieldset disabled={command.busy} className="contents">
        {command.feedback}
        {conflict && (
          <ActionButton type="button" onClick={reload}>
            Load current version; keep my draft
          </ActionButton>
        )}
        {current && (
          <p className={ui.notice}>
            Current saved version {version}: {current.title}, {current.status},
            due {current.due_on}. Your draft is retained below; review it before
            saving.
          </p>
        )}
        <div className={ui.fieldGrid}>
          <label className={ui.field}>
            Title
            <TextInput
              name="title"
              defaultValue={task.title}
              required
              maxLength={250}
            />
          </label>
          <label className={ui.field}>
            Status
            <SelectControl name="status" defaultValue={task.status}>
              {rights.statuses
                .filter((status) => status !== 'completed')
                .map((status) => (
                  <option key={status} value={status}>
                    {status.replaceAll('_', ' ')}
                  </option>
                ))}
            </SelectControl>
          </label>
          <label className={ui.field}>
            Due date
            <TextInput
              name="due_on"
              type="date"
              defaultValue={task.due_on}
              required
            />
          </label>
          <label className={ui.field}>
            Planned date
            <TextInput
              name="planned_on"
              type="date"
              defaultValue={task.planned_on ?? ''}
            />
          </label>
          <AssigneeSelect initial={task.assignee_id} setId={task.set_id} />
          <label className={`${ui.field} md:col-span-2`}>
            Instructions
            <TextArea
              name="description"
              defaultValue={task.description}
              maxLength={5000}
            />
          </label>
          <label className={`${ui.field} md:col-span-2`}>
            Reason for change (required)
            <TextInput name="reason" required maxLength={1000} />
          </label>
        </div>
        <div className={ui.actions}>
          <ActionButton
            className={ui.primary}
            disabled={command.busy || conflict}
          >
            Save Task
          </ActionButton>
        </div>
      </fieldset>
    </form>
  );
}
function CompleteTask({ task, changed }: { task: Task; changed: () => void }) {
  const command = useCommand();
  const [version, setVersion] = useState(task.lock_version);
  const [conflict, setConflict] = useState(false);
  const [current, setCurrent] = useState<Task | null>(null);
  async function reload() {
    const latest = await request<Task>(`${taskBase}/${task.task_id}`);
    setCurrent(latest);
    setVersion(latest.lock_version);
    setConflict(false);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const url = string(data, 'evidence_url');
    try {
      await command.run(`${taskBase}/${task.task_id}/completion`, 'POST', {
        lock_version: version,
        completed_at: string(data, 'completed_at') + ':00Z',
        summary: string(data, 'summary'),
        processed_count: Number(data.get('processed_count')),
        changed_count: Number(data.get('changed_count')),
        evidence: url
          ? [
              {
                label: string(data, 'evidence_label') || 'Completion evidence',
                url,
              },
            ]
          : [],
      });
      changed();
    } catch (error) {
      if (error instanceof ApiError && error.code === 'stale_version')
        setConflict(true);
      /* Retain completion evidence and retry key. */
    }
  }
  return (
    <form {...command.formProps} onSubmit={submit}>
      <fieldset disabled={command.busy} className="contents">
        {command.feedback}
        {conflict && (
          <ActionButton
            type="button"
            onClick={() => {
              void reload().catch(() => {});
            }}
          >
            Load current version; keep my evidence
          </ActionButton>
        )}
        {current && (
          <p className={ui.notice}>
            Current saved version {version}: {current.title}, {current.status},
            due {current.due_on}. Review this information before completing.{' '}
            <ActionButton type="button" onClick={changed}>
              View saved occurrence
            </ActionButton>
          </p>
        )}
        <p className="text-sm">
          Record completed work. Failed attempts should leave the Task open or
          blocked.{' '}
          {task.recurring
            ? 'Successful completion advances enabled maintenance.'
            : ''}
        </p>
        <div className={ui.fieldGrid}>
          <label className={ui.field}>
            Completed at (UTC)
            <TextInput
              type="datetime-local"
              name="completed_at"
              defaultValue={new Date().toISOString().slice(0, 16)}
              required
            />
          </label>
          <label className={`${ui.field} md:col-span-2`}>
            What was completed? (required)
            <TextArea name="summary" required maxLength={5000} />
          </label>
          <label className={ui.field}>
            Resources processed
            <TextInput
              type="number"
              name="processed_count"
              min="0"
              defaultValue="0"
              required
            />
          </label>
          <label className={ui.field}>
            Resources changed
            <TextInput
              type="number"
              name="changed_count"
              min="0"
              defaultValue="0"
              required
            />
          </label>
          <label className={ui.field}>
            Evidence label
            <TextInput name="evidence_label" maxLength={250} />
          </label>
          <label className={ui.field}>
            Evidence URL
            <TextInput name="evidence_url" type="url" maxLength={2048} />
          </label>
        </div>
        <p className="mt-4 text-sm">
          This occurrence and its completion evidence will be preserved in
          Completed work.
        </p>
        <div className={ui.actions}>
          <ActionButton
            className={ui.primary}
            disabled={
              command.busy ||
              conflict ||
              (current !== null &&
                ['completed', 'cancelled'].includes(current.status))
            }
          >
            Complete Task
          </ActionButton>
        </div>
      </fieldset>
    </form>
  );
}
function activityDescription(event: TaskEvents['items'][number]) {
  const details = event.details;
  if (event.action === 'task.completed')
    return String(details.summary ?? 'Work completed');
  if (event.action === 'task.created')
    return `Due ${details.due_on}${details.recurring ? ' · Recurring maintenance' : ''}`;
  if (event.action === 'maintenance.updated')
    return details.enabled
      ? 'Recurring maintenance enabled or updated.'
      : 'Recurring maintenance paused.';
  const changes = (details.changes ?? {}) as Record<string, unknown>;
  const fields: Record<string, string> = {
    title: 'Title',
    description: 'Instructions',
    due_on: 'Due date',
    planned_on: 'Planned date',
    assignee_id: 'Assignee',
    status: 'Status',
  };
  const names = Object.keys(changes)
    .filter((key) => key in fields)
    .map((key) => fields[key]);
  return `${names.join(', ')} updated. ${String(changes.reason ?? '')}`;
}

function TaskHistory({ taskId }: { taskId: string }) {
  const [offset, setOffset] = useState(0);
  return (
    <Load<TaskEvents>
      url={`${taskBase}/${taskId}/activity?offset=${offset}&limit=20`}
    >
      {(page) => (
        <>
          <ol className="divide-y divide-border">
            {page.items.map((event) => (
              <li key={event.event_id} className="py-3">
                <details>
                  <summary className="cursor-pointer text-sm">
                    {event.action.replaceAll('.', ' ')} · {event.actor_name}
                    <time className="block text-xs text-text-secondary">
                      {new Date(event.recorded_at).toLocaleString()}
                    </time>
                  </summary>
                  <p className="mt-2 whitespace-pre-wrap text-sm">
                    {activityDescription(event)}
                  </p>
                  <p className="mt-1 text-xs text-text-secondary">
                    Occurred {new Date(event.occurred_at).toLocaleString()}
                  </p>
                </details>
              </li>
            ))}
          </ol>
          {page.total > 20 && (
            <div className={ui.pagination}>
              <ActionButton
                disabled={!offset}
                onClick={() => setOffset(offset - 20)}
              >
                Previous activity
              </ActionButton>
              <ActionButton
                disabled={offset + 20 >= page.total}
                onClick={() => setOffset(offset + 20)}
              >
                Next activity
              </ActionButton>
            </div>
          )}
        </>
      )}
    </Load>
  );
}

export function NewPeriodPage() {
  return (
    <DraftBoundary>
      <NewPeriodPageContent />
    </DraftBoundary>
  );
}
function NewPeriodPageContent() {
  const command = useCommand();
  const navigate = useNavigate();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const result = await command.run<Period>(
        '/api/v1/admin/work-periods',
        'POST',
        {
          name: string(data, 'name'),
          starts_on: string(data, 'starts_on'),
          ends_on: string(data, 'ends_on'),
        }
      );
      navigate(
        `/work?view=completed&starts_on=${result.starts_on}&ends_on=${result.ends_on}`
      );
    } catch {
      /* Preserve inputs. */
    }
  }
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to="/work?view=completed">
        ← Completed work
      </Link>
      <h1>Save reporting period</h1>
      <p>
        Choose the exact dates for a semester, project period, or other
        reporting window.
      </p>
      <form
        {...command.formProps}
        onSubmit={submit}
        className={`${ui.form} max-w-xl`}
      >
        <fieldset disabled={command.busy} className="contents">
          {command.feedback}
          <div className={ui.fieldGrid}>
            <label className={`${ui.field} md:col-span-2`}>
              Name
              <TextInput
                name="name"
                required
                maxLength={120}
                placeholder="Spring Semester 2027"
              />
            </label>
            <label className={ui.field}>
              Starts on
              <TextInput type="date" name="starts_on" required />
            </label>
            <label className={ui.field}>
              Ends on
              <TextInput type="date" name="ends_on" required />
            </label>
          </div>
          <div className={ui.actions}>
            <ActionButton className={ui.primary} disabled={command.busy}>
              Save period
            </ActionButton>
          </div>
        </fieldset>
      </form>
    </main>
  );
}
