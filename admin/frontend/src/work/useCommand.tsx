import { useContext, useEffect, useId, useRef, useState } from 'react';
import { ActionButton } from '../ui/controls';
import { ui } from '../ui/styles';
import { ApiError, request } from './api';
import { Drafts } from './draftContext';

export function useCommand() {
  const draft = useContext(Drafts)!;
  const id = useId();
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [issues, setIssues] = useState<{ field: string; message: string }[]>(
    []
  );
  const [busy, setBusy] = useState(false);
  const receipt = useRef<{ body: string; key: string; path: string } | null>(
    null
  );
  const alert = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (error) alert.current?.focus();
  }, [error, issues]);
  async function run<T>(path: string, method: string, payload: unknown) {
    const body = JSON.stringify(payload);
    if (receipt.current?.body !== body || receipt.current.path !== path)
      receipt.current = { body, key: crypto.randomUUID(), path };
    setError('');
    setIssues([]);
    let started = false;
    try {
      draft.begin(id);
      started = true;
      setBusy(true);
      const result = await request<T>(path, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-GEOMG-Request': '1',
          'Idempotency-Key': receipt.current.key,
        },
        body,
      });
      receipt.current = null;
      draft.clear(id);
      setDirty(false);
      return result;
    } catch (error) {
      setError((error as Error).message);
      setIssues(error instanceof ApiError ? error.fields : []);
      throw error;
    } finally {
      if (started) draft.end(id);
      setBusy(false);
    }
  }
  return {
    run,
    busy,
    error,
    formProps: {
      onChange() {
        draft.mark(id);
        setDirty(true);
      },
      onReset() {
        draft.clear(id);
        setDirty(false);
        setError('');
      },
    },
    feedback: (
      <>
        {error && (
          <div ref={alert} tabIndex={-1} role="alert" className={ui.error}>
            {error}
            {issues.length > 0 && (
              <ul className="mt-2 list-disc pl-5">
                {issues.map((issue, index) => (
                  <li key={index}>
                    {issue.field ? `${issue.field.replaceAll('_', ' ')}: ` : ''}
                    {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {dirty && (
          <ActionButton
            type="reset"
            disabled={busy}
            className={`${ui.secondary} mb-4`}
          >
            Discard form changes
          </ActionButton>
        )}
      </>
    ),
  };
}
