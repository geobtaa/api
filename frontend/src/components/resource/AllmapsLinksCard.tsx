import { ExternalLink, Layers, PencilLine } from 'lucide-react';
import { scheduleAnalyticsBatch } from '../../services/analytics';
import {
  type AllmapsAttributes,
  getAllmapsEditorUrl,
  getAllmapsViewerUrl,
} from '../../utils/allmaps';

interface AllmapsLinksCardProps {
  allmaps: AllmapsAttributes | null | undefined;
  resourceId?: string;
  searchId?: string;
}

export function AllmapsLinksCard({
  allmaps,
  resourceId,
  searchId,
}: AllmapsLinksCardProps) {
  const viewerUrl = getAllmapsViewerUrl(allmaps);
  const editorUrl = getAllmapsEditorUrl(allmaps);

  if (!viewerUrl && !editorUrl) return null;

  const trackClick = (
    label: string,
    destinationUrl: string,
    eventType: 'allmaps_viewer_click' | 'allmaps_editor_click'
  ) => {
    scheduleAnalyticsBatch({
      events: [
        {
          event_type: eventType,
          search_id: searchId,
          resource_id: resourceId,
          label,
          destination_url: destinationUrl,
          source_component: 'AllmapsLinksCard',
        },
      ],
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Map Overlay</h2>
      </div>
      <div className="divide-y divide-gray-200">
        {viewerUrl && (
          <a
            href={viewerUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() =>
              trackClick(
                'View map in the Allmaps viewer',
                viewerUrl,
                'allmaps_viewer_click'
              )
            }
            className="flex items-center gap-3 px-6 py-4 text-sm font-medium text-blue-600 hover:bg-gray-50 hover:text-blue-800 hover:underline"
          >
            <Layers className="h-5 w-5 shrink-0 text-gray-400" />
            <span className="min-w-0 flex-1">
              View map in the Allmaps viewer
            </span>
            <ExternalLink className="h-4 w-4 shrink-0 text-gray-400" />
          </a>
        )}
        {editorUrl && (
          <a
            href={editorUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() =>
              trackClick(
                'Edit map control points with Allmaps editor',
                editorUrl,
                'allmaps_editor_click'
              )
            }
            className="flex items-center gap-3 px-6 py-4 text-sm font-medium text-blue-600 hover:bg-gray-50 hover:text-blue-800 hover:underline"
          >
            <PencilLine className="h-5 w-5 shrink-0 text-gray-400" />
            <span className="min-w-0 flex-1">
              Edit map control points with Allmaps editor
            </span>
            <ExternalLink className="h-4 w-4 shrink-0 text-gray-400" />
          </a>
        )}
      </div>
      <div className="border-t border-gray-200 bg-gray-50 px-6 py-3">
        <a
          href="https://allmaps.org"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-blue-700 hover:underline"
        >
          <Layers className="h-4 w-4" />
          Allmaps
        </a>
      </div>
    </div>
  );
}
