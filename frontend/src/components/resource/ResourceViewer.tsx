import { useEffect, useRef, useState } from 'react';
import type { GeoBlacklightSchemaAardvark, OgmRecord } from 'ogm-viewer/lib';

interface ResourceViewerProps {
  data: {
    id?: string;
    attributes: {
      ogm?: Record<string, unknown> & {
        id?: string;
        dct_title_s?: string;
        gbl_resourceClass_sm?: string[];
        dct_accessRights_s?: string;
        gbl_mdVersion_s?: string;
        dct_references_s?: string | Record<string, unknown>;
        gbl_mdversion_s?: string;
      };
    };
  };
}

type OgmViewerElement = HTMLElement & {
  loadRecord(record: OgmRecord): Promise<void>;
  theme: 'light' | 'dark';
};

function toAardvarkRecord(data: ResourceViewerProps['data']) {
  const ogm = data.attributes.ogm ?? {};
  const references = ogm.dct_references_s;

  return {
    ...ogm,
    id: ogm.id ?? data.id ?? '',
    dct_title_s: ogm.dct_title_s ?? '',
    gbl_resourceClass_sm: ogm.gbl_resourceClass_sm ?? [],
    dct_accessRights_s:
      ogm.dct_accessRights_s === 'Restricted' ? 'Restricted' : 'Public',
    gbl_mdVersion_s: ogm.gbl_mdVersion_s ?? ogm.gbl_mdversion_s ?? 'Aardvark',
    dct_references_s:
      typeof references === 'string'
        ? references
        : JSON.stringify(references ?? {}),
  } as unknown as GeoBlacklightSchemaAardvark;
}

export function ResourceViewer({ data }: ResourceViewerProps) {
  const viewerRef = useRef<OgmViewerElement | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const viewerElement = viewerRef.current;
    let cancelled = false;

    async function loadViewer() {
      setReady(false);
      setError(false);

      try {
        await import('ogm-viewer');
        const [{ OgmRecord }, { s: setOgmViewerAssetBase }] = await Promise.all(
          [
            import('ogm-viewer/lib'),
            import('ogm-viewer/components/p-BbMGvQFJ.js'),
          ]
        );
        setOgmViewerAssetBase('/ogm-viewer/');
        await customElements.whenDefined('ogm-viewer');

        if (cancelled || !viewerElement) return;

        const handlePreviewsLoading = () => setReady(false);
        const handlePreviewsLoaded = () => setReady(true);
        viewerElement.addEventListener(
          'previewsLoading',
          handlePreviewsLoading
        );
        viewerElement.addEventListener('previewsLoaded', handlePreviewsLoaded);
        await viewerElement.loadRecord(new OgmRecord(toAardvarkRecord(data)));

        return () => {
          viewerElement.removeEventListener(
            'previewsLoading',
            handlePreviewsLoading
          );
          viewerElement.removeEventListener(
            'previewsLoaded',
            handlePreviewsLoaded
          );
        };
      } catch (viewerError) {
        if (cancelled) return;
        console.error('Failed to load OGM viewer:', viewerError);
        setError(true);
      }
    }

    let removeViewerListeners: (() => void) | undefined;
    void loadViewer().then((removeListeners) => {
      if (cancelled) {
        removeListeners?.();
        return;
      }
      removeViewerListeners = removeListeners;
    });

    return () => {
      cancelled = true;
      removeViewerListeners?.();
    };
  }, [data]);

  return (
    <div className="sticky top-[88px] min-h-[600px]">
      {!ready && !error && (
        <div
          className="viewer flex h-[600px] items-center justify-center text-gray-500"
          role="status"
        >
          Loading viewer…
        </div>
      )}
      {error && (
        <div
          className="viewer flex h-[600px] items-center justify-center bg-gray-50 text-gray-500"
          role="alert"
        >
          Item viewer unavailable.
        </div>
      )}
      <ogm-viewer
        ref={viewerRef}
        className={ready ? 'block h-[600px] w-full' : 'hidden'}
        theme="light"
      />
    </div>
  );
}
