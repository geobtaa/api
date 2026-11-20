import { resourcePath, resourceApiPath, decodeId } from '../urlIds';
import { ui } from '../ui/styles';
import { TextInput, TextArea, ActionButton } from '../ui/controls';
import { useEffect, useRef, useState } from 'react';
import { Link, useBeforeUnload, useBlocker, useParams } from 'react-router';
import { request, type SetRecord } from '../sets/api';
import type { Resource } from '../resources/ResourcePages';

type Choice = { id: string; title: string; source_id?: string };
export function MembershipPage({
  mode,
}: {
  mode: 'representative' | 'association';
}) {
  const { setId, resourceId } = useParams();
  const id = mode === 'representative' ? setId! : decodeId(resourceId ?? '');
  return <Editor key={`${mode}:${id}`} mode={mode} id={id} />;
}
function Editor({
  mode,
  id,
}: {
  mode: 'representative' | 'association';
  id: string;
}) {
  const representative = mode === 'representative';
  const [source, setSource] = useState<SetRecord | Resource | null>(null);
  const unassigned = source && !representative && source.set_id === null;
  const [choice, setChoice] = useState<Choice | null>(null);
  const [clear, setClear] = useState(false);
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const key = useRef<string | null>(null);
  const summary = useRef<HTMLParagraphElement>(null);
  const dirty = !saved && (!!choice || clear || !!reason || busy);
  const blocker = useBlocker(dirty);
  useEffect(() => {
    if (blocker.state === 'blocked' && saved) blocker.proceed();
  }, [blocker, saved]);
  useBeforeUnload((event) => {
    if (dirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  useEffect(() => {
    if (error) summary.current?.focus();
  }, [error]);
  const back = representative ? `/sets/${id}` : `${resourcePath(id)}`;
  useEffect(() => {
    let active = true;
    request<SetRecord | Resource>(
      representative ? `/api/v1/admin/sets/${id}` : resourceApiPath(id)
    )
      .then((value) => {
        if (active) {
          setSource(value);
          setError('');
        }
      })
      .catch(() => {
        if (active)
          setError('Record unavailable. Check your access and retry.');
      });
    return () => {
      active = false;
    };
  }, [id, representative, retry]);
  function changed() {
    key.current = null;
    setConfirmed(false);
    setError('');
  }
  async function save() {
    if (!source || !confirmed || !reason.trim() || (!choice && !clear)) return;
    key.current ??= crypto.randomUUID();
    setBusy(true);
    setError('');
    try {
      await request(
        representative
          ? `/api/v1/admin/sets/${id}/representative`
          : `${resourceApiPath(id)}/set`,
        {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Idempotency-Key': key.current,
            'X-GEOMG-Request': '1',
          },
          body: JSON.stringify(
            representative
              ? {
                  resource_id: clear ? null : choice!.id,
                  lock_version: source.lock_version,
                  reason,
                }
              : {
                  source_set_id: source.set_id,
                  target_set_id: choice!.id,
                  resource_version: source.lock_version,
                  reason,
                  confirmed: true,
                }
          ),
        }
      );
      setSaved(true);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main-content" className={ui.page}>
      <h1>
        {representative
          ? 'Set representative'
          : unassigned
            ? 'Assign to a Set'
            : 'Resource Set association'}
      </h1>
      <Link className={ui.backLink} to={back}>
        Back to record
      </Link>
      {blocker.state === 'blocked' && (
        <section
          className={ui.error}
          role="alert"
          aria-label="Unsaved association"
        >
          <p>Discard unsaved association changes?</p>
          <ActionButton onClick={() => blocker.reset()}>
            Keep editing
          </ActionButton>
          <ActionButton disabled={busy} onClick={() => blocker.proceed()}>
            Discard and leave
          </ActionButton>
        </section>
      )}
      {error && (
        <p className={ui.error} ref={summary} tabIndex={-1} role="alert">
          {error}
        </p>
      )}
      {!source && (
        <ActionButton onClick={() => setRetry((v) => v + 1)}>
          Retry record
        </ActionButton>
      )}
      {saved ? (
        <p className={ui.notice} role="status">
          Association saved with Activity evidence.{' '}
          <Link to={back}>View updated record</Link>
        </p>
      ) : !representative &&
        source &&
        'metadata' in source &&
        !source.can_associate ? (
        <p className={ui.notice}>
          Set assignment is unavailable for this Resource.
        </p>
      ) : (
        source && (
          <form
            className={`${ui.form} max-w-4xl`}
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <p>
              {'metadata' in source
                ? String(source.metadata.dct_title_s)
                : source.title}{' '}
              · saved version {source.lock_version}
            </p>
            <fieldset className="grid gap-5" disabled={busy}>
              <legend className="mb-4 text-lg font-semibold">
                {representative
                  ? 'Choose a representative Resource'
                  : 'Choose the managing Set'}
              </legend>
              {representative && (
                <label className={ui.checkbox}>
                  <TextInput
                    type="checkbox"
                    checked={clear}
                    onChange={(event) => {
                      setClear(event.target.checked);
                      changed();
                    }}
                  />
                  Clear the representative link
                </label>
              )}
              {!clear && (
                <SearchChoice
                  kind={representative ? 'resources' : 'sets'}
                  onChoose={(value) => {
                    setChoice(value);
                    changed();
                  }}
                />
              )}
              {choice && !clear && (
                <p>
                  Selected: {choice.title} ({choice.id})
                </p>
              )}
              {!representative && choice && (
                <p>
                  Source: {source.source_id ?? 'Unassigned'} →{' '}
                  {choice.source_id}. The Resource inherits the selected Set’s
                  Source.
                </p>
              )}
              <label htmlFor="association-reason">Reason</label>
              <TextArea
                id="association-reason"
                value={reason}
                maxLength={1000}
                required
                onChange={(event) => {
                  setReason(event.target.value);
                  changed();
                }}
              />
              <p>
                {representative
                  ? 'Changes only the representative link.'
                  : unassigned
                    ? 'The selected Set will manage this draft. Its Activity will record your name and reason.'
                    : 'Moves the current association. Descriptive metadata and publication state are preserved; both Sets receive Activity evidence.'}
              </p>
              <label className={ui.checkbox}>
                <TextInput
                  type="checkbox"
                  checked={confirmed}
                  disabled={!reason.trim() || (!choice && !clear)}
                  onChange={(event) => setConfirmed(event.target.checked)}
                />
                I confirm this association change.
              </label>
              <ActionButton
                className={`${ui.primary} justify-self-start`}
                disabled={!confirmed || busy}
              >
                {busy
                  ? 'Saving…'
                  : unassigned
                    ? 'Assign to a Set'
                    : 'Save association'}
              </ActionButton>
            </fieldset>
            {error && (
              <ActionButton
                type="button"
                className={ui.secondary}
                onClick={() => {
                  key.current = null;
                  setConfirmed(false);
                  setRetry((v) => v + 1);
                }}
              >
                Reload saved version for comparison
              </ActionButton>
            )}
          </form>
        )
      )}
    </main>
  );
}
function SearchChoice({
  kind,
  onChoose,
}: {
  kind: 'resources' | 'sets';
  onChoose: (value: Choice) => void;
}) {
  const [q, setQ] = useState('');
  const [choices, setChoices] = useState<Choice[]>([]);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    request<{ items: (Resource | SetRecord)[] }>(
      `/api/v1/admin/${kind}?q=${encodeURIComponent(q)}&limit=25`
    )
      .then((page) => {
        if (active) {
          setChoices(
            page.items.map((item) =>
              'metadata' in item
                ? { id: item.id, title: String(item.metadata.dct_title_s) }
                : {
                    id: item.set_id,
                    title: item.title,
                    source_id: item.source_id,
                  }
            )
          );
          setError(false);
        }
      })
      .catch(() => {
        if (active) {
          setChoices([]);
          setError(true);
        }
      });
    return () => {
      active = false;
    };
  }, [kind, q]);
  return (
    <div className="grid gap-3">
      <label htmlFor="association-search">Search {kind}</label>
      <TextInput
        id="association-search"
        type="search"
        value={q}
        onChange={(event) => {
          setQ(event.target.value);
          setChoices([]);
        }}
      />
      {error && (
        <p role="alert">Choices unavailable. Change the search to retry.</p>
      )}
      <ul className="max-h-80 space-y-2 overflow-y-auto p-1">
        {choices.map((choice) => (
          <li key={choice.id}>
            <ActionButton
              className={ui.choice}
              type="button"
              onClick={() => onChoose(choice)}
            >
              Choose {choice.title} ({choice.id})
            </ActionButton>
          </li>
        ))}
      </ul>
      <p>Showing up to 25 matches. Refine the search to find another record.</p>
    </div>
  );
}
