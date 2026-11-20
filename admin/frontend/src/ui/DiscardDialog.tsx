import { useRef, useEffect } from 'react';
import { ActionButton } from './controls';
import { ui } from './styles';

export function DiscardDialog({
  busy,
  keep,
  discard,
}: {
  busy: boolean;
  keep: () => void;
  discard: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const keepButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
    keepButton.current?.focus();
  }, []);
  return (
    <dialog
      className={ui.dialog}
      ref={dialog}
      aria-labelledby="discard-heading"
      onCancel={(event) => {
        event.preventDefault();
        keep();
      }}
    >
      <h2 id="discard-heading">
        {busy ? 'Save in progress' : 'Discard unsaved changes?'}
      </h2>
      <p>
        {busy
          ? 'Wait for the save result before leaving this page.'
          : 'Your changes have not been saved.'}
      </p>
      <div className={ui.actions}>
        <ActionButton ref={keepButton} className={ui.primary} onClick={keep}>
          Keep editing
        </ActionButton>
        <ActionButton
          className={ui.secondary}
          disabled={busy}
          onClick={discard}
        >
          Discard changes
        </ActionButton>
      </div>
    </dialog>
  );
}
