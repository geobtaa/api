import {
  type AllmapsAttributes,
  getAllmapsViewerUrl,
} from '../../utils/allmaps';

interface AllmapsOverlayViewerProps {
  allmaps: AllmapsAttributes | null | undefined;
}

export function AllmapsOverlayViewer({ allmaps }: AllmapsOverlayViewerProps) {
  const viewerUrl = getAllmapsViewerUrl(allmaps);

  if (!viewerUrl) {
    return (
      <p className="p-4 text-sm text-gray-600">Map overlay is not available.</p>
    );
  }

  return (
    <div className="h-full">
      <h2 className="sr-only">Allmaps Viewer</h2>
      <iframe
        key={viewerUrl}
        title="Allmaps viewer"
        src={viewerUrl}
        className="block h-[600px] w-full border-0"
        allow="fullscreen; clipboard-write"
        allowFullScreen
        sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox allow-downloads"
        referrerPolicy="strict-origin-when-cross-origin"
      />
    </div>
  );
}
