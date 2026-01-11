import React from 'react';
import { Download, Image } from 'lucide-react';

interface DownloadItem {
  label: string;
  url: string;
  type?: string;
  format?: string;
}

interface DownloadsTableProps {
  downloads: DownloadItem[];
}

export function DownloadsTable({ downloads }: DownloadsTableProps) {
  if (!downloads || downloads.length === 0) return null;

  // Separate IIIF image downloads from other downloads
  const iiifDownloads = downloads.filter(
    (d) => d.type === 'image/jpeg' && d.label.includes('Image')
  );
  const otherDownloads = downloads.filter(
    (d) => !(d.type === 'image/jpeg' && d.label.includes('Image'))
  );

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
            >
              <div className="flex items-center gap-3">
                <Download className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
                <div>
                  <div className="text-sm font-medium text-gray-900 group-hover:text-blue-600">
                    {download.label}
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
