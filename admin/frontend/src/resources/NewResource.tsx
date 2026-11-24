import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';
import { loadImportSets, type SetRecord } from '../sets/api';
import { Load } from '../sources/SourceBrowse';
import {
  ActionButton,
  SelectControl,
  TextArea,
  TextInput,
} from '../ui/controls';
import { ui } from '../ui/styles';
import { resourcePath } from '../urlIds';
import { DraftBoundary } from '../work/DraftBoundary';
import { useCommand } from '../work/useCommand';

type Capabilities = { can_create: boolean; can_choose_set: boolean };

export function NewResource() {
  const [params] = useSearchParams();
  const initialSet = params.get('set_id') ?? '';
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <main id="main-content" className={ui.page}>
      <Link
        className={ui.backLink}
        to={
          initialSet
            ? `/resources?set_id=${encodeURIComponent(initialSet)}`
            : '/resources'
        }
      >
        ← Resources
      </Link>
      <h1 ref={heading} tabIndex={-1}>
        New Resource
      </h1>
      <Load<Capabilities> url="/api/v1/admin/contracts/resources">
        {(rights) =>
          rights.can_create ? (
            <DraftBoundary>
              <CreateForm
                initialSet={initialSet}
                canChooseSet={rights.can_choose_set}
              />
            </DraftBoundary>
          ) : (
            <p className={ui.notice}>
              Resource creation permission is required.
            </p>
          )
        }
      </Load>
    </main>
  );
}

function CreateForm({
  initialSet,
  canChooseSet,
}: {
  initialSet: string;
  canChooseSet: boolean;
}) {
  const navigate = useNavigate();
  const command = useCommand();
  const [setId, setSetId] = useState(initialSet);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    try {
      const result = await command.run<{ id: string }>(
        '/api/v1/admin/resources',
        'POST',
        {
          id: fields.get('id'),
          title: fields.get('title'),
          description: String(fields.get('description') ?? '').trim() || null,
          set_id: setId || null,
        }
      );
      navigate(resourcePath(result.id), { replace: true });
    } catch {
      // The command displays the error and preserves the draft for retry.
    }
  }
  return (
    <form
      className={`${ui.form} max-w-3xl`}
      {...command.formProps}
      onSubmit={submit}
      onReset={() => {
        command.formProps.onReset();
        setSetId(initialSet);
      }}
    >
      <fieldset disabled={command.busy}>
        <div className={ui.fieldGrid}>
          <label className={ui.field}>
            Resource ID (required)
            <TextInput name="id" required maxLength={512} />
          </label>
          <label className={ui.field}>
            Title (required)
            <TextInput name="title" required maxLength={10000} />
          </label>
          <label className={`${ui.field} md:col-span-2`}>
            Description
            <TextArea name="description" rows={3} maxLength={100000} />
          </label>
          {(canChooseSet || initialSet) && (
            <SetField
              value={setId}
              change={setSetId}
              canChooseSet={canChooseSet}
            />
          )}
        </div>
        <div className={ui.actions}>
          <ActionButton className={ui.primary} type="submit">
            {command.busy ? 'Creating draft…' : 'Create draft'}
          </ActionButton>
          {command.feedback}
        </div>
      </fieldset>
    </form>
  );
}

function SetField({
  value,
  change,
  canChooseSet,
}: {
  value: string;
  change: (id: string) => void;
  canChooseSet: boolean;
}) {
  const [choices, setChoices] = useState<SetRecord[]>([]);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!canChooseSet) return;
    const controller = new AbortController();
    loadImportSets(controller.signal)
      .then((items) => {
        if (!controller.signal.aborted)
          setChoices(items.filter((item) => item.status !== 'retired'));
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      });
    return () => controller.abort();
  }, [canChooseSet, retry]);
  return (
    <div>
      <label className={ui.field}>
        Managing Set (optional)
        <SelectControl
          value={value}
          onChange={(event) => change(event.target.value)}
        >
          <option value="">No managing Set</option>
          {value && !choices.some((item) => item.set_id === value) && (
            <option value={value}>{value}</option>
          )}
          {choices.map((item) => (
            <option key={item.set_id} value={item.set_id}>
              {item.title} ({item.set_id})
            </option>
          ))}
        </SelectControl>
      </label>
      {failed && (
        <div role="alert" className={ui.notice}>
          Could not load Sets.{' '}
          <ActionButton
            type="button"
            onClick={() => {
              setFailed(false);
              setRetry(retry + 1);
            }}
          >
            Retry
          </ActionButton>
        </div>
      )}
    </div>
  );
}
