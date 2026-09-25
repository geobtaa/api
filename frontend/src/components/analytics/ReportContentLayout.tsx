import { useEffect, useRef, useState, type ReactNode } from 'react';

type Section = { id: string; label: string };

export function ReportContentLayout({
  report,
  children,
}: {
  report: string;
  children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  const [sections, setSections] = useState<Section[]>([]);
  const [active, setActive] = useState('');

  useEffect(() => {
    const content = root.current?.querySelector('.analytics-content');
    if (!content) return;
    let targets: HTMLElement[] = [];
    let frame = 0;
    const updateActive = () => {
      frame = 0;
      if (!targets.length) return;
      let current = targets[0];
      for (const target of targets) {
        if (target.getBoundingClientRect().top <= 140) current = target;
      }
      if (
        window.scrollY + window.innerHeight >=
        document.documentElement.scrollHeight - 4
      ) {
        current = targets[targets.length - 1];
      }
      setActive(current.id);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(updateActive);
    };
    const collect = () => {
      const candidates = [
        ...content.querySelectorAll<HTMLElement>(
          '.analytics-panel, .analytics-report-sources, [data-nav-label]'
        ),
      ];
      const entries: Section[] = [];
      targets = [];
      const used = new Set<string>();
      for (const panel of candidates) {
        if (panel.closest('details')) continue;
        const header = panel.querySelector('.analytics-panel-header');
        const ownHeader =
          header?.closest('.analytics-panel') === panel ? header : null;
        const label =
          panel.dataset.navLabel ||
          (panel.classList.contains('analytics-report-sources')
            ? 'Sources and grouping'
            : ownHeader?.querySelector('h2, h3, span')?.textContent?.trim());
        if (!label) continue;
        let id =
          panel.id ||
          'section-' +
            label
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, '-')
              .replace(/-$/, '');
        const base = id;
        let suffix = 2;
        while (used.has(id)) id = base + '-' + suffix++;
        used.add(id);
        panel.id = id;
        entries.push({ id, label });
        targets.push(panel);
      }
      setSections((previous) =>
        JSON.stringify(previous) === JSON.stringify(entries)
          ? previous
          : entries
      );
      schedule();
    };
    collect();
    const observer = new MutationObserver(collect);
    observer.observe(content, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      observer.disconnect();
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      cancelAnimationFrame(frame);
    };
  }, [report]);

  return (
    <div
      ref={root}
      className={sections.length > 1 ? 'analytics-content-layout' : undefined}
    >
      {children}
      {sections.length > 1 && (
        <aside className="analytics-content-sidebar">
          <nav
            aria-label={`${report} sections`}
            className="analytics-content-nav"
          >
            <h2>On this page</h2>
            <ul>
              {sections.map(({ id, label }) => (
                <li key={id}>
                  <a
                    href={`#${id}`}
                    aria-current={active === id ? 'location' : undefined}
                    onClick={() => setActive(id)}
                  >
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </aside>
      )}
    </div>
  );
}
