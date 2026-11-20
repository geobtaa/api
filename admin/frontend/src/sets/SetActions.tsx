import { encodeId } from '../urlIds';
import { useState } from 'react';
import { SetState } from './SetState';
import { Link } from 'react-router';
import { ActionButton } from '../ui/controls';
import { ui } from '../ui/styles';
import { type SetRecord, type SetContract } from './api';

export function SetActions({
  item,
  contract,
  changed,
}: {
  item: SetRecord;
  contract: SetContract;
  changed: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative ml-auto">
      <div className="flex flex-wrap items-center gap-3">
        <SetState item={item} contract={contract} changed={changed} />
        <Link
          className={ui.primary}
          to={`/resources/csv?set_id=${encodeURIComponent(item.set_id)}`}
        >
          Import CSV
        </Link>
        <ActionButton
          aria-expanded={open}
          aria-controls="set-acquisition-actions"
          onClick={() => setOpen(!open)}
          className={ui.secondary}
        >
          More import options
        </ActionButton>
      </div>
      {open && (
        <section
          id="set-acquisition-actions"
          aria-label="Harvest and import actions"
          className="absolute right-0 z-20 mt-2 w-[min(24rem,calc(100vw-2rem))] rounded-lg border border-border bg-surface p-4 shadow-xl"
          onKeyDown={(event) => {
            if (event.key === 'Escape') setOpen(false);
          }}
        >
          <Link
            className={ui.secondary}
            to={`/resources/csv/distributions?set_id=${encodeURIComponent(item.set_id)}`}
          >
            Import Distribution links
          </Link>
          {contract.update && (
            <Link
              className="mt-3 block text-sm text-active hover:underline"
              to={`/sets/${encodeId(item.set_id)}/edit#set-workflow_catalog_id`}
            >
              Configure workflow
            </Link>
          )}
        </section>
      )}
    </div>
  );
}
