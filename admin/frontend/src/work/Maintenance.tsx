import { useState, type FormEvent } from 'react';
import { AssigneeSelect } from './AssigneeSelect';
import { DraftBoundary } from './DraftBoundary';
import { useCommand } from './useCommand';
import { Link, useParams } from 'react-router';
import { Load } from '../sources/SourceBrowse';
import { ActionButton, SelectControl, TextInput } from '../ui/controls';
import { ui } from '../ui/styles';
import { decodeId, encodeId } from '../urlIds';
import { type Maintenance, type WorkContract } from './api';

export function MaintenancePage() {
  return (
    <DraftBoundary>
      <MaintenanceContent />
    </DraftBoundary>
  );
}
function MaintenanceContent() {
  const { setId: key } = useParams();
  const setId = decodeId(key ?? '');
  const [revision, setRevision] = useState(0);
  return (
    <main id="main-content" className={ui.page}>
      <Link className={ui.backLink} to={`/sets/${encodeId(setId)}`}>
        ← Set
      </Link>
      <Load<{ title: string; status: string }>
        url={`/api/v1/admin/sets/${encodeURIComponent(setId)}`}
      >
        {(set) => (
          <>
            <p className={ui.kicker}>Set maintenance</p>
            <h1>{set.title}</h1>
            <p>
              Each review or ingest is a separate Task. Successful completion
              advances the next occurrence; failed work stays open.
            </p>
            <Link
              className={ui.secondary}
              to={`/work?set_id=${encodeURIComponent(setId)}`}
            >
              View this Set’s work
            </Link>
            {set.status !== 'active' && (
              <p className={ui.notice}>
                This Set is {set.status}. Activate it before enabling
                maintenance.
              </p>
            )}
            <Load<WorkContract> url="/api/v1/admin/contracts/tasks">
              {(rights) => (
                <Load<Maintenance[]>
                  key={revision}
                  url={`/api/v1/admin/sets/${encodeURIComponent(setId)}/maintenance`}
                >
                  {(rules) => (
                    <div className="mt-6 grid items-start gap-6 lg:grid-cols-2">
                      {['review', 'ingest'].map((type) => (
                        <MaintenanceForm
                          key={type}
                          setId={setId}
                          type={type}
                          initial={rules.find(
                            (rule) => rule.work_type === type
                          )}
                          editable={rights.configure}
                          changed={() => setRevision(revision + 1)}
                        />
                      ))}
                    </div>
                  )}
                </Load>
              )}
            </Load>
          </>
        )}
      </Load>
    </main>
  );
}
function MaintenanceForm({
  setId,
  type,
  initial,
  editable,
  changed,
}: {
  setId: string;
  type: string;
  initial?: Maintenance;
  editable: boolean;
  changed: () => void;
}) {
  const command = useCommand();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body = {
      lock_version: initial?.lock_version ?? 0,
      interval: `P${data.get('amount')}${data.get('unit')}`,
      enabled: data.get('enabled') === 'on',
      next_due_on: String(data.get('next_due_on')) || null,
      assignee_id: String(data.get('assignee_id') ?? '') || null,
    };
    try {
      await command.run(
        `/api/v1/admin/sets/${encodeURIComponent(setId)}/maintenance/${type}`,
        'PUT',
        body
      );
      changed();
    } catch {
      /* Keep draft and retry key. */
    }
  }
  return (
    <form
      {...command.formProps}
      onSubmit={submit}
      className={ui.panel}
      aria-label={`${type} maintenance`}
    >
      <h2>{type === 'review' ? 'Periodic review' : 'Periodic ingest'}</h2>
      {command.feedback}
      <fieldset disabled={!editable || command.busy} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <label className={ui.field}>
            Repeat every
            <TextInput
              type="number"
              name="amount"
              defaultValue={
                initial?.interval.slice(1, -1) ??
                (type === 'review' ? '6' : '1')
              }
              required
              min="1"
              max="1000"
            />
          </label>
          <label className={ui.field}>
            Interval unit
            <SelectControl
              name="unit"
              defaultValue={initial?.interval.slice(-1) ?? 'M'}
            >
              <option value="D">Days</option>
              <option value="W">Weeks</option>
              <option value="M">Months</option>
              <option value="Y">Years</option>
            </SelectControl>
          </label>
        </div>
        <label className={ui.field}>
          First Task due date
          <TextInput
            type="date"
            name="next_due_on"
            required={!initial}
            aria-describedby={`${type}-due-help`}
          />
        </label>
        <p id={`${type}-due-help`} className="text-sm text-text-secondary">
          Only supply when there is no open occurrence. Change an existing
          Task’s due date in Work.
        </p>
        <AssigneeSelect
          setId={setId}
          initial={initial?.assignee_id}
          label="Assign future Tasks to"
        />
        <label className={ui.checkbox}>
          <TextInput
            type="checkbox"
            name="enabled"
            defaultChecked={initial?.enabled ?? true}
          />
          Generate recurring work
        </label>
        <p className="text-sm text-text-secondary">
          Pausing keeps open Tasks and completed history. It does not cancel
          existing work.
        </p>
        {editable && (
          <ActionButton className={ui.primary}>
            {command.busy ? 'Saving…' : 'Save maintenance'}
          </ActionButton>
        )}
      </fieldset>
      {!editable && (
        <p className={ui.notice}>
          Maintenance configuration permission is required.
        </p>
      )}
    </form>
  );
}
