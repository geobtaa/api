import { encodeId } from '../urlIds';
import { ui } from '../ui/styles';
import { TextInput, ActionButton } from '../ui/controls';
import { useState } from 'react';
import { Link } from 'react-router';
import { Load, Pages } from './SourceBrowse';
import { sourceBase, type Page, type Source } from './api';

export function SourcePicker({
  compact = false,
  value,
  saved,
  canRead,
  canUse,
  change,
}: {
  compact?: boolean;
  value: string | null;
  saved: string | null;
  canRead: boolean;
  canUse: boolean;
  change: (id: string | null) => void;
}) {
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(false);
  return (
    <section
      className={
        compact
          ? 'flex flex-wrap items-center gap-2 border-b border-border bg-surface-subtle px-4 py-2 text-sm [&>p]:m-0 [&>button]:px-3 [&>button]:py-1 [&>button]:text-xs [&_li]:my-1'
          : 'border-b border-border p-4 sm:p-6 [&_li]:my-2 [&>button]:mr-2 [&>button]:mb-2'
      }
      aria-labelledby="resource-source-heading"
    >
      <h2
        id="resource-source-heading"
        className={compact ? 'sr-only' : undefined}
      >
        Source
      </h2>
      <p>
        Saved Source:{' '}
        {saved ? (
          canRead ? (
            <Link to={`/sources/${encodeId(saved)}`}>{saved}</Link>
          ) : (
            <code>{saved}</code>
          )
        ) : (
          'Unmapped'
        )}
      </p>
      {value !== saved && (
        <p role="status">Selected Source: {value ?? 'Unmapped'} (unsaved)</p>
      )}
      {canUse && (
        <>
          <ActionButton
            type="button"
            className={ui.secondary}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            {open ? 'Hide Source choices' : 'Choose Source'}
          </ActionButton>
          {value !== null && (
            <ActionButton
              type="button"
              className={ui.secondary}
              onClick={() => change(null)}
            >
              Clear Source
            </ActionButton>
          )}
          {value !== saved && (
            <ActionButton
              type="button"
              className={ui.secondary}
              onClick={() => change(saved)}
            >
              Undo Source change
            </ActionButton>
          )}
          {open && (
            <div className="mt-2 grid w-full gap-3">
              <label htmlFor="resource-source-search">
                Search Sources by title or ID
              </label>
              <div className={ui.inline}>
                <TextInput
                  id="resource-source-search"
                  type="search"
                  maxLength={200}
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      event.preventDefault();
                      setQ(search.trim());
                      setOffset(0);
                    }
                  }}
                />
                <ActionButton
                  type="button"
                  className={ui.secondary}
                  onClick={() => {
                    setQ(search.trim());
                    setOffset(0);
                  }}
                >
                  Find Sources
                </ActionButton>
              </div>
              <Load<Page<Source>>
                url={`${sourceBase}?${new URLSearchParams({ q, offset: String(offset), limit: '10' })}`}
              >
                {(page) => (
                  <>
                    {page.items.length ? (
                      <ul className="max-h-80 overflow-y-auto p-1">
                        {page.items.map((item) => (
                          <li key={item.source_id}>
                            <ActionButton
                              type="button"
                              className={ui.choice}
                              aria-pressed={value === item.source_id}
                              onClick={() => change(item.source_id)}
                            >
                              {item.title} — {item.source_id}
                            </ActionButton>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p>No Sources found.</p>
                    )}
                    <Pages
                      page={page}
                      label="Source choice pages"
                      change={setOffset}
                    />
                  </>
                )}
              </Load>
            </div>
          )}
        </>
      )}
    </section>
  );
}
