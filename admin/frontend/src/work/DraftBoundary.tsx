import { useRef, useState, type ReactNode } from 'react';
import { useBeforeUnload, useBlocker } from 'react-router';
import { DiscardDialog } from '../ui/DiscardDialog';
import { Drafts } from './draftContext';

/** One navigation blocker per page, including pages with multiple Work forms. */
export function DraftBoundary({ children }: { children: ReactNode }) {
  const dirty = useRef(new Set<string>());
  const pending = useRef(new Set<string>());
  const [saving, setSaving] = useState(false);
  const blocked = () => dirty.current.size > 0 || pending.current.size > 0;
  const blocker = useBlocker(blocked);
  useBeforeUnload((event) => {
    if (blocked()) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  return (
    <Drafts.Provider
      value={{
        mark(id) {
          dirty.current.add(id);
        },
        clear(id) {
          dirty.current.delete(id);
        },
        begin(id) {
          if (
            [...dirty.current].some((other) => other !== id) ||
            pending.current.size
          ) {
            throw new Error(
              'Save or discard changes in the other form before continuing.'
            );
          }
          pending.current.add(id);
          setSaving(true);
        },
        end(id) {
          pending.current.delete(id);
          setSaving(pending.current.size > 0);
        },
      }}
    >
      {children}
      {blocker.state === 'blocked' && (
        <DiscardDialog
          busy={saving}
          keep={() => blocker.reset()}
          discard={() => blocker.proceed()}
        />
      )}
    </Drafts.Provider>
  );
}
