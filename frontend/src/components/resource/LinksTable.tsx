import { useState } from 'react';
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
} from 'lucide-react';

interface LinkItem {
  label: string;
  url: string;
}

interface LinksTableProps {
  links: Record<string, LinkItem[]>;
}

export function LinksTable({ links }: LinksTableProps) {
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxContent, setLightboxContent] = useState<{
    category: string;
    items: LinkItem[];
  } | null>(null);

  if (!links || Object.keys(links).length === 0) return null;

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
    // Categories that should open in lightbox
    const lightboxCategories = ['Web Services', 'Metadata'];

    if (lightboxCategories.includes(category)) {
      setLightboxContent({ category, items });
      setLightboxOpen(true);
    } else {
      // For other categories, use the first link as the main link
      if (items.length > 0) {
        window.open(items[0].url, '_blank', 'noopener,noreferrer');
      }
    }
  };

  const closeLightbox = () => {
    setLightboxOpen(false);
    setLightboxContent(null);
  };

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
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 bg-gray-50 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">
                {lightboxContent.category}
              </h3>
              <button
                onClick={closeLightbox}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              <div className="space-y-3">
                {lightboxContent.items.map((link, index) => (
                  <a
                    key={index}
                    href={link.url}
                    className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-blue-300 transition-colors group"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <ExternalLink className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
                    <div className="flex-1">
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
            </div>
          </div>
        </div>
      )}
    </>
  );
}
