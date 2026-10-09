import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ExternalLink, Maximize, Minimize } from 'lucide-react';

interface AllmapsViewerFrameProps {
  tabs: ReactNode;
  viewerUrl: string | null;
  children: ReactNode;
}

/** Keeps viewer actions beside the tabs and supports browsers without Fullscreen API. */
export function AllmapsViewerFrame({
  tabs,
  viewerUrl,
  children,
}: AllmapsViewerFrameProps) {
  const container = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const onFullscreenChange = () => {
      if (!document.fullscreenElement) setExpanded(false);
    };
    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () =>
      document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  useEffect(() => {
    if (!expanded) return;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    toggle.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.fullscreenElement) {
        setExpanded(false);
        toggle.current?.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [expanded]);

  async function toggleFullscreen() {
    if (expanded) {
      if (document.fullscreenElement === container.current) {
        await document.exitFullscreen();
      }
      setExpanded(false);
      return;
    }
    setExpanded(true);
    try {
      await container.current?.requestFullscreen?.();
    } catch {
      // Embedded browsers may reject fullscreen; the viewport expansion still works.
    }
  }

  return (
    <div
      ref={container}
      className={
        expanded
          ? 'fixed inset-0 z-[10000] flex h-dvh w-full flex-col bg-white'
          : 'bg-white rounded-lg shadow-md overflow-hidden'
      }
    >
      {(tabs || viewerUrl || expanded) && (
        <div className="flex flex-wrap items-center justify-between gap-x-4 border-b border-gray-200 bg-white px-4 pt-3 shrink-0">
          {tabs}
          {(viewerUrl || expanded) && (
            <div className="ml-auto flex items-center gap-4 py-3 text-sm">
              <button
                ref={toggle}
                type="button"
                onClick={() => void toggleFullscreen()}
                aria-pressed={expanded}
                className="inline-flex items-center gap-1.5 text-blue-600 hover:underline"
              >
                {expanded ? (
                  <Minimize className="h-4 w-4 shrink-0" aria-hidden="true" />
                ) : (
                  <Maximize className="h-4 w-4 shrink-0" aria-hidden="true" />
                )}
                {expanded ? 'Exit fullscreen' : 'Fullscreen'}
              </button>
              {viewerUrl && (
                <a
                  href={viewerUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-blue-600 hover:underline"
                >
                  <ExternalLink
                    className="h-4 w-4 shrink-0"
                    aria-hidden="true"
                  />
                  Open in new tab
                </a>
              )}
            </div>
          )}
        </div>
      )}
      <div
        className={
          expanded
            ? 'min-h-0 flex-1 [&>div]:h-full [&_iframe]:!h-full [&_iframe]:w-full'
            : undefined
        }
      >
        {children}
      </div>
    </div>
  );
}
