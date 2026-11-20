import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Load } from '../sources/SourceBrowse';
import {
  ActionButton,
  DataTable,
  SelectControl,
  TextInput,
} from '../ui/controls';
import { ui } from '../ui/styles';
import { encodeId } from '../urlIds';
import {
  monthBounds,
  taskBase,
  today,
  type Period,
  type Report,
  type Task,
  type TaskPage,
  type WorkContract,
} from './api';

export function WorkPage() {
  const [params, setParams] = useSearchParams();
  const view = params.get('view') ?? 'queue';
  const month = params.get('month') ?? today().slice(0, 7);
  const [monthStart, monthEnd] = monthBounds(month);
  const starts = params.get('starts_on') ?? monthStart;
  const ends = params.get('ends_on') ?? monthEnd;
  const offset = Number(params.get('offset') ?? 0);
  function filter(key: string, value: string) {
    setParams((previous) => {
      const next = new URLSearchParams(previous);
      next.delete('offset');
      if (value) next.set(key, value);
      else next.delete(key);
      return next;
    });
  }
  const query = new URLSearchParams({
    offset: String(offset),
    limit: '100',
    status: view === 'completed' ? 'completed' : 'pending',
  });
  for (const key of [
    'q',
    'work_type',
    'set_id',
    'source_id',
    'assignee_id',
    'unassigned',
  ]) {
    if (params.get(key)) query.set(key, params.get(key)!);
  }
  if (view === 'completed') {
    query.set('completed_from', starts);
    query.set('completed_to', ends);
  }
  if (view === 'calendar') {
    query.set('calendar_from', monthStart);
    query.set('calendar_to', monthEnd);
  }
  if (params.get('overdue') === 'true' && view === 'queue') {
    const date = new Date(today() + 'T00:00:00Z');
    date.setUTCDate(date.getUTCDate() - 1);
    query.set('due_to', date.toISOString().slice(0, 10));
  }
  const report = new URLSearchParams(query);
  ['status', 'completed_from', 'completed_to'].forEach((k) => report.delete(k));
  report.set('offset', '0');
  report.set('starts_on', starts);
  report.set('ends_on', ends);
  report.set('group_by', params.get('group_by') ?? 'set');
  return (
    <main id="main-content" className={ui.page}>
      <div className={ui.toolbar}>
        <div>
          <p className={ui.kicker}>Maintenance and stewardship</p>
          <h1>Work</h1>
        </div>
        <Load<WorkContract> url="/api/v1/admin/contracts/tasks">
          {(rights) => (
            <>
              {rights.create && (
                <Link
                  className={ui.primary}
                  to={`/tasks/new${params.get('set_id') ? `?set_id=${params.get('set_id')}` : ''}`}
                >
                  New Task
                </Link>
              )}
            </>
          )}
        </Load>
      </div>
      <nav aria-label="Work views" className="mb-6 flex flex-wrap gap-2">
        {['queue', 'calendar', 'completed'].map((mode) => (
          <Link
            key={mode}
            className={mode === view ? ui.primary : ui.secondary}
            aria-current={mode === view ? 'page' : undefined}
            to={`/work?${new URLSearchParams({ ...Object.fromEntries(params), view: mode, offset: '0' })}`}
          >
            {mode === 'queue'
              ? 'Queue'
              : mode === 'calendar'
                ? 'Calendar'
                : 'Completed'}
          </Link>
        ))}
      </nav>
      <Load<WorkContract> url="/api/v1/admin/contracts/tasks">
        {(rights) => (
          <>
            <form
              className={ui.search}
              onSubmit={(event) => {
                event.preventDefault();
                filter(
                  'q',
                  String(new FormData(event.currentTarget).get('q') ?? '')
                );
              }}
            >
              <div className="flex flex-wrap items-end gap-3">
                <label className={`${ui.field} min-w-48 flex-1`}>
                  Find work
                  <TextInput name="q" defaultValue={params.get('q') ?? ''} />
                </label>
                <label className={ui.field}>
                  Work type
                  <SelectControl
                    value={params.get('work_type') ?? ''}
                    onChange={(e) => filter('work_type', e.target.value)}
                  >
                    <option value="">All types</option>
                    {rights.work_types.map((type) => (
                      <option key={type}>{type}</option>
                    ))}
                  </SelectControl>
                </label>
                <ActionButton type="submit">Search</ActionButton>
              </div>
            </form>
            {view === 'queue' && (
              <div className="my-4 flex flex-wrap gap-4">
                <label className={ui.checkbox}>
                  <TextInput
                    type="checkbox"
                    checked={params.get('overdue') === 'true'}
                    onChange={(e) =>
                      filter('overdue', e.target.checked ? 'true' : '')
                    }
                  />
                  Overdue only
                </label>
                <label className={ui.checkbox}>
                  <TextInput
                    type="checkbox"
                    checked={params.get('unassigned') === 'true'}
                    onChange={(e) =>
                      filter('unassigned', e.target.checked ? 'true' : '')
                    }
                  />
                  Unassigned only
                </label>
              </div>
            )}
            {view === 'calendar' && (
              <label className={`${ui.field} mb-5 max-w-xs`}>
                Calendar month
                <TextInput
                  type="month"
                  value={month}
                  onChange={(e) => filter('month', e.target.value)}
                />
              </label>
            )}
            {view === 'completed' && (
              <>
                <div className="my-5 flex flex-wrap items-end gap-4">
                  <label className={ui.field}>
                    Completed from (UTC)
                    <TextInput
                      type="date"
                      value={starts}
                      onChange={(e) => filter('starts_on', e.target.value)}
                    />
                  </label>
                  <label className={ui.field}>
                    Completed through (UTC)
                    <TextInput
                      type="date"
                      value={ends}
                      onChange={(e) => filter('ends_on', e.target.value)}
                    />
                  </label>
                  <Load<Period[]> url="/api/v1/admin/work-periods?limit=500">
                    {(periods) => (
                      <label className={ui.field}>
                        Reporting period
                        <SelectControl
                          value={
                            periods.find(
                              (period) =>
                                period.starts_on === starts &&
                                period.ends_on === ends
                            )?.period_id ?? ''
                          }
                          onChange={(e) => {
                            const period = periods.find(
                              (p) => p.period_id === e.target.value
                            );
                            if (period)
                              setParams((previous) => {
                                const next = new URLSearchParams(previous);
                                next.set('starts_on', period.starts_on);
                                next.set('ends_on', period.ends_on);
                                next.delete('offset');
                                return next;
                              });
                          }}
                        >
                          <option value="">Choose a saved period</option>
                          {periods.map((period) => (
                            <option
                              key={period.period_id}
                              value={period.period_id}
                            >
                              {period.name}
                            </option>
                          ))}
                        </SelectControl>
                      </label>
                    )}
                  </Load>
                  <label className={ui.field}>
                    Group accomplishments by
                    <SelectControl
                      value={params.get('group_by') ?? 'set'}
                      onChange={(e) => filter('group_by', e.target.value)}
                    >
                      <option value="set">Set</option>
                      <option value="source">Source</option>
                      <option value="work_type">Work type</option>
                      <option value="completed_by">Completing staff</option>
                    </SelectControl>
                  </label>
                  {rights.configure && (
                    <Link className={ui.secondary} to="/work/periods/new">
                      Save reporting period
                    </Link>
                  )}
                </div>
                <p className="text-sm text-text-secondary">
                  Reports use when work was completed. Due dates and recording
                  dates remain separate. Counts total Task activity; a Resource
                  may occur in more than one Task.
                </p>
                {rights.report && (
                  <ReportTable key={report.toString()} query={report} />
                )}
              </>
            )}
            <Load<TaskPage> url={`${taskBase}?${query}`}>
              {(page) => (
                <>
                  <p role="status">
                    {page.total.toLocaleString()}{' '}
                    {view === 'completed' ? 'completed Tasks' : 'Tasks'}
                    {params.get('set_id') ? ' in this Set' : ''}
                  </p>
                  {page.total === 0 ? (
                    <p className={ui.notice}>
                      {view === 'completed'
                        ? 'No completed work in this date range.'
                        : 'No work matches these filters.'}
                    </p>
                  ) : view === 'calendar' ? (
                    <Calendar month={month} items={page.items} />
                  ) : (
                    <TaskTable
                      items={page.items}
                      completed={view === 'completed'}
                    />
                  )}
                  {page.total > 0 && (
                    <div className={ui.pagination} aria-label="Task pagination">
                      <ActionButton
                        disabled={offset === 0}
                        onClick={() =>
                          filter('offset', String(Math.max(0, offset - 100)))
                        }
                      >
                        Previous
                      </ActionButton>
                      <span>
                        {offset + 1}–{Math.min(offset + 100, page.total)} of{' '}
                        {page.total} Tasks
                      </span>
                      <ActionButton
                        disabled={offset + 100 >= page.total}
                        onClick={() => filter('offset', String(offset + 100))}
                      >
                        Next
                      </ActionButton>
                    </div>
                  )}
                </>
              )}
            </Load>
          </>
        )}
      </Load>
    </main>
  );
}

function TaskTable({
  items,
  completed,
}: {
  items: Task[];
  completed: boolean;
}) {
  return (
    <div className={ui.tableRegion}>
      <DataTable>
        <caption className="sr-only">
          {completed ? 'Completed work' : 'Work queue'}
        </caption>
        <thead>
          <tr>
            <th>Task</th>
            <th>Set / Source</th>
            <th>Status</th>
            <th>Due</th>
            <th>{completed ? 'Completed' : 'Assignee'}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((task) => (
            <tr key={task.task_id}>
              <th scope="row">
                <Link to={`/tasks/${task.task_id}`}>{task.title}</Link>
                <small className="block font-normal">
                  {task.work_type}
                  {task.recurring ? ' · Recurring' : ''}
                </small>
              </th>
              <td>
                <Link to={`/sets/${encodeId(task.set_id)}`}>
                  {task.set_title}
                </Link>
                <small className="block">{task.source_title}</small>
              </td>
              <td>{task.status.replaceAll('_', ' ')}</td>
              <td>
                {task.due_on}
                {!completed && task.due_on < today() && (
                  <strong className="block text-danger">Overdue</strong>
                )}
              </td>
              <td>
                {completed ? (
                  <>
                    {task.completed_at?.slice(0, 10)}
                    <small className="block">{task.completed_by_name}</small>
                  </>
                ) : (
                  (task.assignee_name ?? 'Unassigned')
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </div>
  );
}

function Calendar({ month, items }: { month: string; items: Task[] }) {
  const [start, end] = monthBounds(month);
  const first = new Date(start + 'T00:00:00Z').getUTCDay();
  const days = Number(end.slice(-2));
  return (
    <section
      aria-label="Work calendar"
      className="overflow-x-auto rounded-lg border border-border bg-surface"
    >
      <p className="px-4 pt-3 text-sm">
        Planned date, or due date when no planned date is set. Pagination
        applies to calendar entries.
      </p>
      <div className="grid min-w-[700px] grid-cols-7">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
          <div
            key={day}
            className="border-b border-border p-2 text-sm font-semibold"
          >
            {day}
          </div>
        ))}
        {Array.from({ length: first }, (_, i) => (
          <div
            key={`blank-${i}`}
            aria-hidden="true"
            className="border-b border-border bg-surface-muted"
          />
        ))}
        {Array.from({ length: days }, (_, i) => {
          const day = month + '-' + String(i + 1).padStart(2, '0');
          return (
            <section
              key={day}
              aria-label={day}
              className="min-h-28 border-r border-b border-border p-2"
            >
              <h2
                className={`mb-2 text-sm ${day === today() ? 'font-bold text-active' : ''}`}
              >
                <time dateTime={day}>{i + 1}</time>
              </h2>
              <ul className="space-y-2">
                {items
                  .filter((task) => (task.planned_on ?? task.due_on) === day)
                  .map((task) => (
                    <li key={task.task_id} className="text-xs">
                      <Link
                        className="font-medium text-active hover:underline"
                        to={`/tasks/${task.task_id}`}
                      >
                        {task.title}
                      </Link>
                      <span className="block text-text-secondary">
                        {task.assignee_name ?? 'Unassigned'} ·{' '}
                        {task.status.replaceAll('_', ' ')}
                      </span>
                    </li>
                  ))}
              </ul>
            </section>
          );
        })}
      </div>
    </section>
  );
}

function ReportTable({ query }: { query: URLSearchParams }) {
  const [offset, setOffset] = useState(0);
  const params = new URLSearchParams(query);
  params.set('offset', String(offset));
  return (
    <Load<Report> url={`${taskBase}/report?${params}`}>
      {(report) => (
        <section aria-label="Completed work report" className="my-5">
          <p className="text-base font-semibold">
            {report.completed} completed · {report.processed.toLocaleString()}{' '}
            Resources processed · {report.changed.toLocaleString()} changed ·{' '}
            {report.late} completed late
          </p>
          <div className={ui.tableRegion}>
            <DataTable>
              <thead>
                <tr>
                  <th>Group</th>
                  <th>Completed</th>
                  <th>Processed</th>
                  <th>Changed</th>
                  <th>Late</th>
                </tr>
              </thead>
              <tbody>
                {report.groups.map((group) => (
                  <tr key={group.key}>
                    <th scope="row">{group.label}</th>
                    <td>{group.completed}</td>
                    <td>{group.processed}</td>
                    <td>{group.changed}</td>
                    <td>{group.late}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          {report.total_groups > 100 && (
            <div className={ui.pagination}>
              <ActionButton
                disabled={!offset}
                onClick={() => setOffset(offset - 100)}
              >
                Previous groups
              </ActionButton>
              <span>
                {offset + 1}–{Math.min(offset + 100, report.total_groups)} of{' '}
                {report.total_groups}
              </span>
              <ActionButton
                disabled={offset + 100 >= report.total_groups}
                onClick={() => setOffset(offset + 100)}
              >
                Next groups
              </ActionButton>
            </div>
          )}
        </section>
      )}
    </Load>
  );
}
