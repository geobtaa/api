import React from 'react';
import { Download, Image } from 'lucide-react';
import { useState } from 'react';
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
}

interface DownloadsTableProps {
  downloads: DownloadItem[];
  resourceId?: string;
  searchId?: string;
}

export function DownloadsTable({
  downloads,
  resourceId,
  searchId,
}: DownloadsTableProps) {
  const [preparing, setPreparing] = useState<Record<string, boolean>>({});
  const [failed, setFailed] = useState<Record<string, boolean>>({});

  if (!downloads || downloads.length === 0) return null;

  // Separate IIIF image downloads from other downloads
  const iiifDownloads = downloads.filter(
    (d) => d.type === 'image/jpeg' && d.label.includes('Image')
  );
  const otherDownloads = downloads.filter(
    (d) => !(d.type === 'image/jpeg' && d.label.includes('Image'))
  );

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
                error instanceof Error ? error.message : 'unknown_prepare_error',
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
        {/* IIIF Image Downloads - Horizontal */}
        {iiifDownloads.length > 0 && (
          <div className="px-6 py-4">
            <div className="flex items-center gap-2 mb-2">
              <Image className="w-5 h-5 text-gray-400" />
              <span className="text-sm font-medium text-gray-900">
                Download Image
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {iiifDownloads.map((download, index) => (
                <a
                  key={index}
                  href={download.url}
                  className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() =>
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
                    })
                  }
                >
                  {download.label.replace(' Image', '')}
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
