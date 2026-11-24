import React from 'react';
import { viewerImageDownloads } from '../../utils/viewerImageDownloads';
import {
  imageSourceKey,
  type ImageSelection,
  type ImageNavigation,
} from '../../utils/iiifSelection';
import { Download } from 'lucide-react';
import { useEffect, useId, useState } from 'react';
import { getApiBasePath } from '../../services/api';
import { scheduleAnalyticsBatch } from '../../services/analytics';

interface DownloadItem {
  label: string;
  url: string;
  type?: string;
  format?: string;
  generated?: boolean;
  generation_path?: string;
  download_type?: string;
  source?: string;
  canvas_id?: string;
  canvas_label?: string;
  image_source?: string;
  image_occurrences?: number[];
  iiif_resource_url?: string;
}

interface DownloadsTableProps {
  downloads: DownloadItem[];
  resourceId?: string;
  searchId?: string;
  resolveIiif?: boolean;
  followViewer?: boolean;
  activeImage?: ImageSelection | null;
  onImageNavigate?: (request: ImageNavigation) => void;
}

export function DownloadsTable({
  downloads,
  resourceId,
  searchId,
  resolveIiif = false,
  followViewer = false,
  activeImage = null,
  onImageNavigate,
}: DownloadsTableProps) {
  const [preparing, setPreparing] = useState<Record<string, boolean>>({});
  const [failed, setFailed] = useState<Record<string, boolean>>({});

  const [resolved, setResolved] = useState<DownloadItem[] | null>(null);
  const resolveManifest = resolveIiif && !followViewer;
  const [loading, setLoading] = useState(resolveManifest);
  const [iiifError, setIiifError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [selectedCanvas, setSelectedCanvas] = useState('');
  const selectId = useId();

  useEffect(() => {
    setResolved(null);
    setSelectedCanvas('');
    setIiifError(false);
    if (!resolveManifest || !resourceId) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    const base = getApiBasePath().replace(/\/$/, '');
    fetch(`${base}/resources/${encodeURIComponent(resourceId)}/downloads`, {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to load IIIF downloads');
        const payload = (await response.json()) as {
          downloads: DownloadItem[];
          iiif_error?: boolean;
        };
        if (!Array.isArray(payload.downloads))
          throw new Error('Invalid downloads');
        if (!controller.signal.aborted) {
          setResolved(payload.downloads);
          setIiifError(Boolean(payload.iiif_error));
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setIiifError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [resolveManifest, resourceId, attempt]);

  const allDownloads = resolved ?? downloads ?? [];
  const isIiif = (d: DownloadItem) =>
    (d.source === 'iiif' &&
      (d.canvas_id ||
        d.image_source ||
        (!d.iiif_resource_url && d.type?.startsWith('image/')))) ||
    (!d.source && d.type === 'image/jpeg' && d.label.includes('Image'));
  const iiifDownloads = allDownloads.filter(isIiif);
  const otherDownloads = allDownloads.filter((d) => !isIiif(d));
  const canvases = Array.from(
    new Map(
      iiifDownloads.map((d) => [
        d.canvas_id || 'image',
        d.canvas_label || 'Image',
      ])
    )
  );
  const activeCanvas = canvases.some(([id]) => id === selectedCanvas)
    ? selectedCanvas
    : canvases[0]?.[0];
  const sourceMatches =
    activeImage?.image && activeImage.resourceId === resourceId
      ? iiifDownloads.filter(
          (d) =>
            imageSourceKey(d.image_source) ===
              imageSourceKey(activeImage.image?.url) &&
            Boolean(d.image_source) &&
            imageSourceKey(d.iiif_resource_url) ===
              imageSourceKey(activeImage.resourceUrl)
        )
      : [];
  // A repeated scan can belong to several canvases. Never guess its page-specific files.
  const distinctCanvases = new Set(sourceMatches.map((d) => d.canvas_id));
  const matchingImages = sourceMatches.filter((d) =>
    activeImage?.image?.occurrence !== undefined && d.image_occurrences
      ? d.image_occurrences.includes(activeImage.image.occurrence)
      : distinctCanvases.size <= 1
  );
  const matchingCanvases = new Set(
    matchingImages.map((d) => d.canvas_id).filter(Boolean)
  );
  const matchedImages = followViewer
    ? iiifDownloads.filter(
        (d) =>
          matchingImages.includes(d) ||
          (!d.image_source &&
            d.canvas_id &&
            matchingCanvases.has(d.canvas_id) &&
            imageSourceKey(d.iiif_resource_url) ===
              imageSourceKey(activeImage?.resourceUrl))
      )
    : iiifDownloads.filter((d) => (d.canvas_id || 'image') === activeCanvas);

  // Viewer mode never requests a second manifest traversal. The opened service is authoritative.
  const visibleImages =
    followViewer && activeImage?.image?.service
      ? viewerImageDownloads(activeImage, resourceId)
      : matchedImages;

  const viewerPages =
    activeImage && activeImage.resourceId === resourceId
      ? (activeImage.sequence ?? [])
      : [];
  const viewerPageOptions = viewerPages.map((page) => {
    const download = iiifDownloads.find(
      (d) =>
        imageSourceKey(d.iiif_resource_url) ===
          imageSourceKey(activeImage?.resourceUrl) &&
        imageSourceKey(d.image_source) === imageSourceKey(page.url) &&
        (!d.image_occurrences || d.image_occurrences.includes(page.occurrence))
    );
    return {
      ...page,
      label: download?.canvas_label || `Image ${page.index + 1}`,
    };
  });

  if (
    !allDownloads.length &&
    !resolveManifest &&
    !viewerPages.length &&
    !visibleImages.length
  )
    return null;

  const resolveDownloadLabel = (download: DownloadItem): string => {
    if (!download.generated) return download.label;

    const key = download.generation_path || download.url;
    if (preparing[key]) return `Preparing download (${download.label})...`;
    if (failed[key]) return `Download failed (${download.label}) - retry`;
    return download.label;
  };

  const handleGeneratedDownload = async (
    event: React.MouseEvent<HTMLAnchorElement>,
    download: DownloadItem
  ) => {
    if (!download.generated) {
      scheduleAnalyticsBatch({
        events: [
          {
            event_type: 'download_click',
            search_id: searchId,
            resource_id: resourceId,
            label: download.label,
            destination_url: download.url,
            source_component: 'DownloadsTable',
            properties: {
              generated: false,
              download_type: download.download_type,
              format: download.format,
            },
          },
        ],
      });
      return;
    }
    event.preventDefault();

    const key = download.generation_path || download.url;
    const apiBasePath = getApiBasePath().replace(/\/$/, '');
    const toApiUrl = (rawPath: string): string => {
      if (rawPath.startsWith('http')) return rawPath;

      const normalizedPath = rawPath.startsWith('/') ? rawPath : `/${rawPath}`;
      // Avoid /api/v1/api/v1/... when payload paths are already API-rooted.
      const pathWithoutApiPrefix = normalizedPath.startsWith('/api/v1/')
        ? normalizedPath.slice('/api/v1'.length)
        : normalizedPath;

      return `${apiBasePath}${pathWithoutApiPrefix}`;
    };

    const prepareUrl = toApiUrl(key);
    if (preparing[key]) return;

    setPreparing((prev) => ({ ...prev, [key]: true }));
    setFailed((prev) => ({ ...prev, [key]: false }));

    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'download_prepare_requested',
          search_id: searchId,
          resource_id: resourceId,
          label: download.label,
          destination_url: prepareUrl,
          source_component: 'DownloadsTable',
          properties: {
            generated: true,
            download_type: download.download_type,
            format: download.format,
          },
        },
      ],
    });

    try {
      const response = await fetch(prepareUrl, {
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        const errText = await response.text();
        throw new Error(
          `Failed to prepare generated download (${response.status}): ${errText.slice(0, 200)}`
        );
      }

      const contentType = response.headers.get('content-type') || '';
      if (!contentType.toLowerCase().includes('application/json')) {
        const body = await response.text();
        throw new Error(
          `Prepare endpoint returned non-JSON response: ${body.slice(0, 200)}`
        );
      }

      const payload = (await response.json()) as { download_url?: string };
      const rawDownloadUrl = payload.download_url || `${key}/file`;
      const downloadUrl = toApiUrl(rawDownloadUrl);
      scheduleAnalyticsBatch({
        events: [
          {
            event_type: 'download_prepare_success',
            search_id: searchId,
            resource_id: resourceId,
            label: download.label,
            destination_url: downloadUrl,
            source_component: 'DownloadsTable',
            properties: {
              generated: true,
              download_type: download.download_type,
              format: download.format,
            },
          },
          {
            event_type: 'download_click',
            search_id: searchId,
            resource_id: resourceId,
            label: download.label,
            destination_url: downloadUrl,
            source_component: 'DownloadsTable',
            properties: {
              generated: true,
              download_type: download.download_type,
              format: download.format,
            },
          },
        ],
      });
      window.open(downloadUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Failed to prepare generated download:', error);
      setFailed((prev) => ({ ...prev, [key]: true }));
      scheduleAnalyticsBatch({
        events: [
          {
            event_type: 'download_prepare_failure',
            search_id: searchId,
            resource_id: resourceId,
            label: download.label,
            destination_url: prepareUrl,
            source_component: 'DownloadsTable',
            properties: {
              generated: true,
              download_type: download.download_type,
              format: download.format,
              error:
                error instanceof Error
                  ? error.message
                  : 'unknown_prepare_error',
            },
          },
        ],
      });
    } finally {
      setPreparing((prev) => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Downloads</h2>
      </div>
      <div className="divide-y divide-gray-200">
        {loading && (
          <p role="status" className="px-6 py-4 text-sm text-gray-600">
            Loading image downloads…
          </p>
        )}
        {iiifError && (
          <div className="px-6 py-4 text-sm text-gray-600" role="status">
            Image downloads could not be loaded.{' '}
            <button
              type="button"
              className="text-blue-600 hover:underline"
              onClick={() => setAttempt((value) => value + 1)}
            >
              Retry
            </button>
          </div>
        )}
        {!loading && !iiifError && resolveManifest && !iiifDownloads.length && (
          <p className="px-6 py-4 text-sm text-gray-600">
            No downloadable images were found in this IIIF item.
          </p>
        )}
        {(iiifDownloads.length > 0 ||
          visibleImages.length > 0 ||
          viewerPages.length > 1) && (
          <div className="px-6 py-4">
            {visibleImages.length > 0 && (
              <div className="text-sm font-medium text-gray-500 mb-2">
                {followViewer
                  ? 'Download current image'
                  : canvases.length > 1
                    ? 'Download Images'
                    : 'Download Image'}
              </div>
            )}
            {followViewer && viewerPageOptions.length > 1 && (
              <div className="mb-3">
                <label htmlFor={selectId} className="sr-only">
                  Page or sheet ({viewerPageOptions.length})
                </label>
                <select
                  id={selectId}
                  aria-describedby={`${selectId}-help`}
                  value={
                    activeImage?.pageIndex ?? activeImage?.image?.index ?? ''
                  }
                  disabled={!onImageNavigate}
                  onChange={(event) => {
                    const page = viewerPages.find(
                      (page) => page.index === Number(event.target.value)
                    );
                    if (page && activeImage)
                      onImageNavigate?.({
                        previewId: activeImage.previewId,
                        resourceId: activeImage.resourceId,
                        resourceUrl: activeImage.resourceUrl,
                        renderer: 'image',
                        index: page.index,
                        url: page.url,
                      });
                  }}
                  className="w-full min-w-0 rounded border border-gray-300 p-2 text-sm"
                >
                  {viewerPageOptions.map((page) => (
                    <option key={page.index} value={page.index}>
                      {page.index + 1}. {page.label}
                    </option>
                  ))}
                </select>
                <p id={`${selectId}-help`} className="sr-only">
                  Choosing a page updates the viewer and its download links.
                </p>
              </div>
            )}
            {!followViewer && canvases.length > 1 && (
              <div className="mb-3">
                <label
                  htmlFor={selectId}
                  className="block text-sm text-gray-700 mb-1"
                >
                  Page or sheet ({canvases.length})
                </label>
                <select
                  id={selectId}
                  value={activeCanvas}
                  onChange={(event) => setSelectedCanvas(event.target.value)}
                  className="w-full min-w-0 rounded border border-gray-300 p-2 text-sm"
                >
                  {canvases.map(([id, name], index) => (
                    <option key={id} value={id}>
                      {index + 1}. {name}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  Downloads apply to the selected page or sheet. Images are
                  downloaded individually.
                </p>
              </div>
            )}
            {followViewer && !visibleImages.length && (
              <p
                className="mb-3 text-sm text-gray-600"
                role="status"
                aria-live="polite"
              >
                {activeImage?.image
                  ? 'No downloads are available for the current image.'
                  : activeImage
                    ? 'Image downloads are available once the current image opens.'
                    : 'Select an image in the item viewer to see its downloads.'}
              </p>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {visibleImages.map((download) => (
                <a
                  key={download.url}
                  href={download.url}
                  className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(event) => handleGeneratedDownload(event, download)}
                >
                  {download.label.replace(/ Image$/, '')}
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Other Downloads - Vertical */}
        {otherDownloads.map((download, index) => (
          <div key={index} className="px-6 py-4 hover:bg-gray-50">
            <a
              href={download.url}
              className="flex items-center justify-between group"
              target="_blank"
              rel="noopener noreferrer"
              onClick={(event) => handleGeneratedDownload(event, download)}
            >
              <div className="flex items-center gap-3">
                <Download className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
                <div>
                  <div className="text-sm font-medium text-gray-900 group-hover:text-blue-600">
                    {resolveDownloadLabel(download)}
                  </div>
                </div>
              </div>
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
