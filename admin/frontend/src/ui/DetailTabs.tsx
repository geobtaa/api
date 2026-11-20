import { useId, useState, type ReactNode } from 'react';

export function DetailTabs({
  tabs,
}: {
  tabs: { label: string; content: ReactNode }[];
}) {
  const [active, setActive] = useState(0);
  const id = useId();
  return (
    <div className="min-w-0 overflow-hidden rounded-lg border border-border bg-surface shadow-xs">
      <div
        role="tablist"
        aria-label="Related information"
        className="flex overflow-x-auto border-b border-border"
      >
        {tabs.map((tab, index) => (
          <button
            key={tab.label}
            type="button"
            role="tab"
            id={`${id}-tab-${index}`}
            aria-controls={`${id}-panel-${index}`}
            aria-selected={active === index}
            tabIndex={active === index ? 0 : -1}
            className="shrink-0 border-b-2 border-transparent px-4 py-3 text-sm font-semibold text-text-secondary aria-selected:border-active aria-selected:text-active focus-visible:outline-2 focus-visible:outline-active"
            onClick={() => setActive(index)}
            onKeyDown={(event) => {
              const next =
                event.key === 'ArrowRight'
                  ? (index + 1) % tabs.length
                  : event.key === 'ArrowLeft'
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === 'Home'
                      ? 0
                      : event.key === 'End'
                        ? tabs.length - 1
                        : null;
              if (next !== null) {
                event.preventDefault();
                setActive(next);
                document.getElementById(`${id}-tab-${next}`)?.focus();
              }
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab, index) => (
        <div
          key={tab.label}
          role="tabpanel"
          id={`${id}-panel-${index}`}
          aria-labelledby={`${id}-tab-${index}`}
          hidden={active !== index}
          tabIndex={0}
          className="p-4 [&>section]:m-0 [&>section]:border-0 [&>section]:p-0 [&_h2]:sr-only"
        >
          {tab.content}
        </div>
      ))}
    </div>
  );
}
