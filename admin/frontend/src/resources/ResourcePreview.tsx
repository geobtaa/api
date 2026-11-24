import { resourceApiPath } from '../urlIds';
import { useEffect, useRef, useState } from 'react';

export function ResourcePreview({
  id,
  version,
}: {
  id: string;
  version: number;
}) {
  return (
    <section
      className="rounded-lg border border-border bg-surface p-4 shadow-xs [&>p]:text-sm [&>p]:text-text-secondary"
      aria-label="Resource preview"
    >
      <h2 className="sr-only">Preview</h2>
      <Viewer key={`${id}:${version}`} id={id} version={version} />
    </section>
  );
}

function Viewer({ id, version }: { id: string; version: number }) {
  const host = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    const container = host.current;
    import('ogm-viewer')
      .then(() => {
        if (!active || !container) return;
        const viewer = document.createElement('ogm-viewer');
        viewer.setAttribute(
          'record-url',
          `${resourceApiPath(id)}/metadata?${new URLSearchParams({ version: String(version) })}`
        );
        viewer.setAttribute('theme', 'light');
        viewer.setAttribute('aria-label', 'Saved Resource OGM viewer');
        container.replaceChildren(viewer);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      container?.replaceChildren();
    };
  }, [id, version]);
  return (
    <>
      {failed ? (
        <p role="alert">Preview could not load. Reload the page to retry.</p>
      ) : (
        <div
          ref={host}
          className="h-[600px] max-h-[70vh] [&_ogm-viewer]:block [&_ogm-viewer]:size-full"
        />
      )}
    </>
  );
}
