import { useState, useEffect } from 'react';
import {
  ExternalLink,
  Link as LinkIcon,
  X,
  FileText,
  Globe,
  Database,
  BookOpen,
  Code,
  MapPin,
  Loader2,
  Download,
} from 'lucide-react';
import { getApiBasePath } from '../../services/api';
import { scheduleAnalyticsBatch } from '../../services/analytics';

interface LinkItem {
  label: string;
  url: string;
  format?: 'iso' | 'fgdc' | 'html';
}

interface LinksTableProps {
  links: Record<string, LinkItem[]>;
  resourceId?: string;
  searchId?: string;
}

export function LinksTable({
  links,
  resourceId,
  searchId,
}: LinksTableProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxContent, setLightboxContent] = useState<{
    category: string;
    items: LinkItem[];
  } | null>(null);
  const [activeMetadataLink, setActiveMetadataLink] = useState<LinkItem | null>(
    null
  );
  const [metadataHtml, setMetadataHtml] = useState<string | null>(null);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);

  const transformableMetadataItems =
    lightboxContent?.category.toLowerCase().includes('metadata') && resourceId
      ? lightboxContent.items.filter((l) => l.format)
      : [];

  // Auto-load first transformable metadata when Metadata lightbox opens
  useEffect(() => {
    if (
      !lightboxOpen ||
      !lightboxContent?.category.toLowerCase().includes('metadata') ||
      !resourceId
    ) {
      return;
    }
    const items = lightboxContent.items.filter((l) => l.format);
    if (items.length === 0) return;
    // Only set on open; avoid overwriting when user has switched tabs
    setActiveMetadataLink((prev) => (prev ? prev : items[0]));
    setMetadataHtml(null);
    setMetadataError(null);
    setMetadataLoading(true);
  }, [
    lightboxOpen,
    lightboxContent?.category,
    lightboxContent?.items,
    resourceId,
  ]);

  // Fetch metadata when active link changes
  useEffect(() => {
    if (!activeMetadataLink?.format || !resourceId) return;

    let cancelled = false;
    setMetadataLoading(true);
    setMetadataError(null);

    const doFetch = async () => {
      try {
        const base = getApiBasePath().replace(/\/$/, '');
        const url = `${base}/resources/${resourceId}/metadata/display?format=${encodeURIComponent(activeMetadataLink.format)}`;
        const fullUrl = url.startsWith('/')
          ? `${window.location.origin}${url}`
          : url;
        const resp = await fetch(fullUrl);
        if (cancelled) return;
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(text || `HTTP ${resp.status}`);
        }
        const html = await resp.text();
        if (cancelled) return;
        setMetadataHtml(html);
      } catch (err) {
        if (cancelled) return;
        setMetadataError(
          err instanceof Error ? err.message : 'Failed to load metadata'
        );
      } finally {
        if (!cancelled) setMetadataLoading(false);
      }
    };

    doFetch();
    return () => {
      cancelled = true;
    };
  }, [activeMetadataLink?.format, activeMetadataLink?.label, resourceId]);

  if (!links || Object.keys(links).length === 0) return null;

  const resolveEventType = (category: string) => {
    const categoryLower = category.toLowerCase();

    if (categoryLower.includes('metadata')) return 'metadata_download';
    if (categoryLower.includes('web services') || categoryLower.includes('api')) {
      return 'web_service_click';
    }
    if (categoryLower.includes('source') || categoryLower.includes('visit')) {
      return 'visit_source_click';
    }
    if (categoryLower.includes('arcgis')) return 'external_geoportal_click';
    if (
      categoryLower.includes('documentation') ||
      categoryLower.includes('document')
    ) {
      return 'documentation_click';
    }
    return 'outbound_link_click';
  };

  const trackLinkClick = (category: string, item: LinkItem) => {
    scheduleAnalyticsBatch({
      events: [
        {
          event_type: resolveEventType(category),
          search_id: searchId,
          resource_id: resourceId,
          label: item.label,
          destination_url: item.url,
          source_component: 'LinksTable',
          properties: {
            category,
            format: item.format,
          },
        },
      ],
    });
  };

  const getCategoryIcon = (category: string) => {
    const categoryLower = category.toLowerCase();

    if (categoryLower.includes('metadata')) {
      return (
        <Database className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    } else if (
      categoryLower.includes('documentation') ||
      categoryLower.includes('document')
    ) {
      return (
        <BookOpen className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    } else if (
      categoryLower.includes('web services') ||
      categoryLower.includes('api')
    ) {
      return (
        <Code className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    } else if (
      categoryLower.includes('source') ||
      categoryLower.includes('visit')
    ) {
      return (
        <Globe className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    } else if (
      categoryLower.includes('download') ||
      categoryLower.includes('file')
    ) {
      return (
        <FileText className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    } else if (
      categoryLower.includes('map') ||
      categoryLower.includes('location')
    ) {
      return (
        <MapPin className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    } else {
      return (
        <LinkIcon className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
      );
    }
  };

  const handleCategoryClick = (category: string, items: LinkItem[]) => {
    const lightboxCategories = ['Web Services', 'Metadata', 'Open in ArcGIS'];

    if (lightboxCategories.includes(category)) {
      setLightboxContent({ category, items });
      setActiveMetadataLink(null);
      setMetadataHtml(null);
      setMetadataError(null);
      setLightboxOpen(true);
    } else {
      if (items.length > 0) {
        trackLinkClick(category, items[0]);
        window.open(items[0].url, '_blank', 'noopener,noreferrer');
      }
    }
  };

  const closeLightbox = () => {
    setLightboxOpen(false);
    setLightboxContent(null);
    setActiveMetadataLink(null);
    setMetadataHtml(null);
    setMetadataError(null);
  };

  const isMetadataLightbox = lightboxContent?.category
    .toLowerCase()
    .includes('metadata');
  const showMetadataView =
    isMetadataLightbox && resourceId && transformableMetadataItems.length > 0;

  return (
    <>
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Links</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {Object.entries(links).map(([category, linkItems]) => (
            <div key={category} className="px-6 py-4 hover:bg-gray-50">
              <button
                onClick={() => handleCategoryClick(category, linkItems)}
                className="flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline group w-full text-left"
              >
                {getCategoryIcon(category)}
                {category}
                <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-blue-500 ml-auto" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Lightbox Modal */}
      {lightboxOpen && lightboxContent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999] p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 bg-gray-50 border-b border-gray-200 shrink-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-lg font-semibold text-gray-900">
                  {lightboxContent.category}
                </h3>
                {/* Format tabs - Metadata only */}
                {showMetadataView && transformableMetadataItems.length > 1 && (
                  <div className="flex gap-1 ml-2" role="tablist">
                    {transformableMetadataItems.map((link) => (
                      <button
                        key={link.format}
                        type="button"
                        role="tab"
                        aria-selected={
                          activeMetadataLink?.format === link.format
                        }
                        onClick={() => setActiveMetadataLink(link)}
                        className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                          activeMetadataLink?.format === link.format
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                        }`}
                      >
                        {link.label
                          .replace(' XML', '')
                          .replace(' Metadata', '')}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {showMetadataView && activeMetadataLink && (
                  <a
                    href={activeMetadataLink.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() =>
                      trackLinkClick(lightboxContent.category, activeMetadataLink)
                    }
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </a>
                )}
                <button
                  onClick={closeLightbox}
                  className="text-gray-400 hover:text-gray-600 transition-colors p-1"
                  aria-label="Close"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto flex-1 min-h-0">
              {showMetadataView ? (
                <>
                  {metadataLoading && (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                    </div>
                  )}
                  {metadataError && !metadataLoading && (
                    <div className="text-red-600 text-sm">{metadataError}</div>
                  )}
                  {metadataHtml && !metadataLoading && (
                    <iframe
                      title={activeMetadataLink?.label ?? 'Metadata'}
                      srcDoc={metadataHtml}
                      className="w-full min-h-[500px] border border-gray-200 rounded-lg"
                      sandbox="allow-same-origin"
                    />
                  )}
                </>
              ) : (
                <div className="space-y-3">
                  {lightboxContent.items.map((link, index) => (
                    <a
                      key={index}
                      href={link.url}
                      onClick={() =>
                        trackLinkClick(lightboxContent.category, link)
                      }
                      className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-blue-300 transition-colors group"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 group-hover:text-blue-600">
                          {link.label}
                        </div>
                        <div className="text-xs text-gray-500 mt-1 break-all">
                          {link.url}
                        </div>
                      </div>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
