import { useEffect, useRef, useState } from 'react';
import { useBeforeUnload, useBlocker } from 'react-router';
import { ActionButton, TextArea, TextInput } from '../ui/controls';
import { DiscardDialog } from '../ui/DiscardDialog';
import { ui } from '../ui/styles';
import {
  request,
  setBase,
  type SetContract,
  type SetRecord,
  type SetStatePreview,
} from './api';

export function SetState({
  item,
  contract,
  changed,
}: {
  item: SetRecord;
  contract: SetContract;
  changed: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<SetStatePreview | null>(null);
  const [reason, setReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const receipt = useRef<{ body: string; key: string } | null>(null);
  const summary = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const allow = useRef(false);
  const blocker = useBlocker(() => !allow.current && (busy || !!reason));
  useBeforeUnload((event) => {
    if (!allow.current && (busy || reason)) event.preventDefault();
  });
  useEffect(() => {
    if (error) summary.current?.focus();
  }, [error]);
  useEffect(() => {
    if (preview) heading.current?.focus();
  }, [preview]);
  const actions =
    contract.state_actions?.filter(
      (action) => action.current === item.status
    ) ?? [];

  async function load(target: string) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError('');
    setConfirmed(false);
    setPreview(null);
    receipt.current = null;
    try {
      setPreview(
        await request<SetStatePreview>(
          `${setBase}/${encodeURIComponent(item.set_id)}/state-preview?target=${encodeURIComponent(target)}`
        )
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  async function apply(event: React.FormEvent) {
    event.preventDefault();
    if (
      pending.current ||
      !preview ||
      !confirmed ||
      !reason.trim() ||
      !preview.can_proceed
    )
      return;
    pending.current = true;
    setBusy(true);
    setError('');
    const body = JSON.stringify({
      target: preview.target,
      lock_version: preview.lock_version,
      reason,
      confirmed,
    });
    if (receipt.current?.body !== body)
      receipt.current = { body, key: crypto.randomUUID() };
    try {
      await request(`${setBase}/${encodeURIComponent(item.set_id)}/state`, {
        method: 'PUT',
        body,
        headers: {
          'Content-Type': 'application/json',
          'X-GEOMG-Request': '1',
          'Idempotency-Key': receipt.current.key,
        },
      });
      allow.current = true;
      setReason('');
      setPreview(null);
      setOpen(false);
      changed();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="relative">
      <ActionButton
        className={ui.secondary}
        aria-expanded={open}
        aria-controls="set-state-panel"
        disabled={busy}
        onClick={() => setOpen(!open)}
      >
        {item.status === 'active'
          ? 'Active'
          : item.status === 'inactive'
            ? 'Inactive'
            : 'Retired'}{' '}
        · Change state
      </ActionButton>
      {open && (
        <section
          id="set-state-panel"
          aria-label="Set state"
          className="absolute right-0 z-30 mt-2 max-h-[80vh] w-[min(28rem,calc(100vw-2rem))] overflow-y-auto rounded-lg border border-border bg-surface p-4 text-left shadow-xl"
        >
          <h2>Set state</h2>
          {!actions.length && <p>No state changes are available.</p>}
          <div className={ui.actions}>
            {actions.map((action) => (
              <ActionButton
                key={action.target}
                className={ui.secondary}
                disabled={busy}
                onClick={() => void load(action.target)}
              >
                {action.label}
              </ActionButton>
            ))}
          </div>
          {busy && <p role="status">Checking Set state…</p>}
          {error && (
            <div ref={summary} role="alert" tabIndex={-1} className={ui.error}>
              <p>{error}</p>
              <p>
                Retry an uncertain result with the same details. If the Set
                changed, refresh the preview and confirm again.
              </p>
            </div>
          )}
          {preview && (
            <form onSubmit={apply}>
              <h3 ref={heading} tabIndex={-1}>
                Review state change for {preview.title}
              </h3>
              <p>
                {preview.current} → {preview.target} · version{' '}
                {preview.lock_version}
              </p>
              <ul>
                {preview.consequences.map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
              {!preview.can_proceed && (
                <p role="alert">
                  Retirement is blocked by {preview.open_tasks} unfinished
                  Task(s) and {preview.active_jobs ?? 0} active job(s).
                </p>
              )}
              <fieldset disabled={busy}>
                <legend className="sr-only">Confirm Set state</legend>
                <div className={ui.field}>
                  <label htmlFor="set-state-reason">Reason (required)</label>
                  <TextArea
                    id="set-state-reason"
                    required
                    maxLength={1000}
                    value={reason}
                    onChange={(event) => {
                      setReason(event.target.value);
                      setConfirmed(false);
                    }}
                  />
                  <label>
                    <TextInput
                      type="checkbox"
                      checked={confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                    />{' '}
                    I confirm this Set state change.
                  </label>
                </div>
                <div className={ui.actions}>
                  <ActionButton
                    className={ui.primary}
                    type="submit"
                    disabled={
                      !confirmed || !reason.trim() || !preview.can_proceed
                    }
                  >
                    Confirm state change
                  </ActionButton>
                  <ActionButton
                    className={ui.secondary}
                    type="button"
                    onClick={() => void load(preview.target)}
                  >
                    Refresh preview
                  </ActionButton>
                  <ActionButton
                    className={ui.secondary}
                    type="button"
                    onClick={() => {
                      setReason('');
                      setConfirmed(false);
                      setPreview(null);
                      setError('');
                      receipt.current = null;
                    }}
                  >
                    Cancel state change
                  </ActionButton>
                </div>
              </fieldset>
            </form>
          )}
        </section>
      )}
      {blocker.state === 'blocked' && (
        <DiscardDialog
          busy={busy}
          keep={() => blocker.reset()}
          discard={() => blocker.proceed()}
        />
      )}
    </div>
  );
}
