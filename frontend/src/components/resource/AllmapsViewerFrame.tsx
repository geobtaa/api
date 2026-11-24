import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import { ExternalLink, Maximize, Minimize } from 'lucide-react';

import {
  ViewerExpandedContext,
  ViewerTabsContext,
  type ViewerPreviewTabs,
} from './viewerFrameContext';

interface AllmapsViewerFrameProps {
  hasItem?: boolean;
  overlayActive?: boolean;
  onShowItem?: () => void;
  onShowOverlay?: () => void;
  viewerUrl: string | null;
  children: ReactNode;
}

/** Keeps viewer actions beside the tabs and supports browsers without Fullscreen API. */
export function AllmapsViewerFrame({
  hasItem = true,
  overlayActive = false,
  onShowItem,
  onShowOverlay,
  viewerUrl,
  children,
}: AllmapsViewerFrameProps) {
  const container = useRef<HTMLDivElement>(null);
  const toggle = useRef<HTMLButtonElement>(null);
  const [expanded, setExpanded] = useState(false);

  const [navigation, setNavigation] = useState<ViewerPreviewTabs | null>(null);
  const panelId = useId();
  const itemTabs = navigation?.tabs ?? [
    { id: 'item', label: 'Item Viewer', active: true, disabled: false },
  ];
  const tabs = hasItem
    ? itemTabs.map((tab) => ({ ...tab, active: tab.active && !overlayActive }))
    : [];
  if (onShowOverlay) {
    tabs.push({
      id: 'allmaps',
      label: 'Map Overlay',
      active: overlayActive,
      disabled: false,
    });
  }
  function activate(id: string) {
    if (id === 'allmaps') {
      onShowOverlay?.();
    } else {
      onShowItem?.();
      navigation?.select(id);
    }
  }
  const activeTabId = tabs.find((tab) => tab.active)?.id;
  function onTabKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const buttons = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>('button:enabled')
    );
    const index = buttons.indexOf(event.target as HTMLButtonElement);
    if (index < 0) return;
    let next: number;
    switch (event.key) {
      case 'ArrowRight':
        next = (index + 1) % buttons.length;
        break;
      case 'ArrowLeft':
        next = (index + buttons.length - 1) % buttons.length;
        break;
      case 'Home':
        next = 0;
        break;
      case 'End':
        next = buttons.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    buttons[next].focus();
    buttons[next].click();
  }

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
      {(tabs.length > 0 || viewerUrl || expanded) && (
        <div className="flex flex-wrap items-center justify-between gap-x-4 border-b border-gray-200 bg-white px-4 shrink-0">
          {tabs.length > 0 && (
            <div
              role="tablist"
              aria-label="Resource previews"
              className="flex flex-wrap items-stretch gap-x-1 self-stretch"
              onKeyDown={onTabKeyDown}
            >
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={panelId + '-' + tab.id}
                  aria-controls={panelId}
                  aria-selected={tab.active}
                  disabled={tab.disabled}
                  tabIndex={tab.active ? 0 : -1}
                  onClick={() => activate(tab.id)}
                  className={`-mb-px border-b-2 px-3 py-3 text-sm font-semibold focus-visible:outline-offset-[-3px] disabled:opacity-50 ${tab.active ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-600 hover:text-gray-900'}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}
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
        id={panelId}
        role={activeTabId ? 'tabpanel' : undefined}
        aria-labelledby={activeTabId ? panelId + '-' + activeTabId : undefined}
        className={
          expanded
            ? 'min-h-0 flex-1 [&>div]:h-full [&_iframe]:!h-full [&_iframe]:w-full'
            : undefined
        }
      >
        <ViewerExpandedContext.Provider value={expanded}>
          <ViewerTabsContext.Provider value={setNavigation}>
            {children}
          </ViewerTabsContext.Provider>
        </ViewerExpandedContext.Provider>
      </div>
    </div>
  );
}
