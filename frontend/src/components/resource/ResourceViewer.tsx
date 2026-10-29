import {
  toAardvarkRecord,
  hasOgmContentPreview,
} from '../../utils/ogmViewerRecord';
import { BASEMAP_STYLES } from '../../config/mapStyles';
import { useEffect, useRef, useState } from 'react';
import type {
  ImageSelection,
  ImageNavigation,
  PreviewSelection,
} from '../../utils/iiifSelection';
import type { OgmRecord } from 'ogm-viewer/lib';

interface ResourceViewerProps {
  imageNavigation?: ImageNavigation | null;
  onImageSelectionChange?: (selection: ImageSelection | null) => void;
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

export function ResourceViewer(props: ResourceViewerProps) {
  const { data, onImageSelectionChange } = props;
  const hasContent = hasOgmContentPreview(data);
  useEffect(() => {
    if (!hasContent) onImageSelectionChange?.(null);
  }, [hasContent, onImageSelectionChange]);
  return hasContent ? <ContentViewer {...props} /> : null;
}

function ContentViewer({
  data,
  onImageSelectionChange,
  imageNavigation,
}: ResourceViewerProps) {
  const selectionCallback = useRef(onImageSelectionChange);
  selectionCallback.current = onImageSelectionChange;
  const activeSelection = useRef<ImageSelection | null>(null);
  const viewerRef = useRef<OgmViewerElement | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const viewerElement = viewerRef.current;
    let cancelled = false;
    let activePreview: PreviewSelection | null = null;
    const images = new Map<string, ImageSelection>();
    const recordId = String(data.attributes.ogm?.id ?? data.id ?? '');
    const publish = () => {
      if (cancelled) return;
      activeSelection.current =
        activePreview?.renderer === 'image'
          ? (images.get(activePreview.previewId) ?? {
              ...activePreview,
              image: null,
            })
          : null;
      selectionCallback.current?.(activeSelection.current);
    };
    const previewChanged = (event: Event) => {
      const detail = (event as CustomEvent<PreviewSelection | null>).detail;
      if (detail && detail.resourceId !== recordId) return;
      activePreview = detail;
      publish();
    };
    const imageChanged = (event: Event) => {
      const detail = (event as CustomEvent<ImageSelection>).detail;
      if (!detail || detail.resourceId !== recordId) return;
      images.set(detail.previewId, detail);
      if (activePreview?.previewId === detail.previewId) publish();
    };
    activeSelection.current = null;
    selectionCallback.current?.(null);

    async function loadViewer() {
      setReady(false);
      setError(false);

      try {
        await import('ogm-viewer');
        const { OgmRecord } = await import('ogm-viewer/lib');
        await customElements.whenDefined('ogm-viewer');

        if (cancelled || !viewerElement) return;

        const handlePreviewsLoading = () => {
          if (!cancelled) {
            setReady(false);
            activePreview = null;
            images.clear();
            publish();
          }
        };
        const handlePreviewsLoaded = () => {
          if (!cancelled) setReady(true);
        };
        viewerElement.addEventListener('previewChange', previewChanged);
        viewerElement.addEventListener('imageChange', imageChanged);
        viewerElement.addEventListener(
          'previewsLoading',
          handlePreviewsLoading
        );
        viewerElement.addEventListener('previewsLoaded', handlePreviewsLoaded);
        removeViewerListeners = () => {
          viewerElement.removeEventListener('previewChange', previewChanged);
          viewerElement.removeEventListener('imageChange', imageChanged);
          viewerElement.removeEventListener(
            'previewsLoading',
            handlePreviewsLoading
          );
          viewerElement.removeEventListener(
            'previewsLoaded',
            handlePreviewsLoaded
          );
        };
        viewerElement.setAttribute('light-basemap', BASEMAP_STYLES.liberty);
        viewerElement.setAttribute('dark-basemap', BASEMAP_STYLES.dark);
        await viewerElement.loadRecord(new OgmRecord(toAardvarkRecord(data)));
      } catch (viewerError) {
        if (cancelled) return;
        removeViewerListeners?.();
        removeViewerListeners = undefined;
        console.error('Failed to load OGM viewer:', viewerError);
        activeSelection.current = null;
        selectionCallback.current?.(null);
        setError(true);
      }
    }

    let removeViewerListeners: (() => void) | undefined;
    void loadViewer();

    return () => {
      cancelled = true;
      removeViewerListeners?.();
    };
  }, [data]);

  useEffect(() => {
    const active = activeSelection.current;
    if (
      !imageNavigation ||
      !active ||
      active.resourceId !== imageNavigation.resourceId ||
      active.previewId !== imageNavigation.previewId ||
      active.resourceUrl !== imageNavigation.resourceUrl ||
      !active.sequence?.some(
        (page) =>
          page.index === imageNavigation.index &&
          page.url === imageNavigation.url
      )
    )
      return;
    viewerRef.current?.dispatchEvent(
      new CustomEvent('imageNavigationRequest', { detail: imageNavigation })
    );
  }, [imageNavigation]);

  return (
    <div className="sticky top-[88px] min-h-[600px]">
      {!ready && !error && (
        <div
          className="viewer pointer-events-none absolute inset-0 z-10 flex h-[600px] items-center justify-center bg-white/70 text-gray-500"
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
        className={error ? 'hidden' : 'block h-[600px] w-full'}
        theme="light"
        omit-location=""
      />
    </div>
  );
}
