import React, { useState } from 'react';
import { Copy, Check, Download } from 'lucide-react';

export type CitationStyle = 'apa' | 'mla' | 'chicago';

interface CitationTableProps {
  /** Primary/default citation (APA format) - for backward compatibility */
  citation: string;
  /** All citation formats: apa, mla, chicago */
  citations?: Partial<Record<CitationStyle, string>>;
  permalink: string;
  /** Resource ID for export links (JSON-LD, RIS, BibTeX) */
  resourceId?: string;
}

function getApiBase(): string {
  const base = import.meta.env.VITE_API_BASE_URL;
  if (base && (base.startsWith('http://') || base.startsWith('https://')))
    return base;
  return '/api/v1';
}

const STYLE_LABELS: Record<CitationStyle, string> = {
  apa: 'APA 7th',
  mla: 'MLA 9th',
  chicago: 'Chicago',
};

export function CitationTable({ citation, citations, permalink, resourceId }: CitationTableProps) {
  const [copiedPermalink, setCopiedPermalink] = useState(false);
  const [copiedCitation, setCopiedCitation] = useState(false);
  const [selectedStyle, setSelectedStyle] = useState<CitationStyle>('apa');

  const styleOptions: CitationStyle[] = citations
    ? (['apa', 'mla', 'chicago'] as const).filter((s) => citations[s])
    : ['apa'];
  const displayCitation =
    citations && selectedStyle in citations && citations[selectedStyle]
      ? citations[selectedStyle]!
      : citation;

  const handleCopyPermalink = async () => {
    try {
      await navigator.clipboard.writeText(permalink);
      setCopiedPermalink(true);
      setTimeout(() => setCopiedPermalink(false), 2000);
    } catch (err) {
      console.error('Failed to copy permalink:', err);
    }
  };

  const handleCopyCitation = async () => {
    try {
      await navigator.clipboard.writeText(displayCitation);
      setCopiedCitation(true);
      setTimeout(() => setCopiedCitation(false), 2000);
    } catch (err) {
      console.error('Failed to copy citation:', err);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden mt-6">
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">
          Cite &amp; Reference
        </h2>
      </div>
      <table className="min-w-full divide-y divide-gray-200">
        <tbody className="divide-y divide-gray-200">
          {(citation || displayCitation) && (
            <tr className="hover:bg-gray-50">
              <td className="px-6 py-4">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="text-sm font-medium text-gray-500">Citation</div>
                  {styleOptions.length > 1 && (
                    <select
                      value={selectedStyle}
                      onChange={(e) => setSelectedStyle(e.target.value as CitationStyle)}
                      className="text-xs border border-gray-300 rounded px-2 py-1 bg-white"
                    >
                      {styleOptions.map((s) => (
                        <option key={s} value={s}>
                          {STYLE_LABELS[s]}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
                <div className="flex gap-2">
                  <div className="flex-1 text-sm text-gray-900">{displayCitation}</div>
                  <button
                    onClick={handleCopyCitation}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    title="Copy citation"
                  >
                    {copiedCitation ? (
                      <Check size={16} className="text-green-500" />
                    ) : (
                      <Copy size={16} />
                    )}
                  </button>
                </div>
              </td>
            </tr>
          )}
          {resourceId && (
            <tr className="hover:bg-gray-50">
              <td className="px-6 py-4">
                <div className="text-sm font-medium text-gray-500 mb-2">
                  Export for citation tools
                </div>
                <div className="flex flex-wrap gap-3">
                  <a
                    href={`${getApiBase()}/resources/${resourceId}/citation/ris`}
                    download={`${resourceId}.ris`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    <Download size={14} />
                    RIS
                  </a>
                  <a
                    href={`${getApiBase()}/resources/${resourceId}/citation/bibtex`}
                    download={`${resourceId}.bib`}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    <Download size={14} />
                    BibTeX
                  </a>
                  <a
                    href={`${getApiBase()}/resources/${resourceId}/citation/json-ld`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                  >
                    JSON-LD
                  </a>
                </div>
                <p className="text-xs text-gray-500 mt-1.5">
                  RIS and BibTeX for Zotero, EndNote, Mendeley. JSON-LD for Schema.org/Google Dataset Search.
                </p>
              </td>
            </tr>
          )}
          <tr className="hover:bg-gray-50">
            <td className="px-6 py-4">
              <div className="text-sm font-medium text-gray-500 mb-1">
                BTAA Geoportal Link
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  readOnly
                  value={permalink}
                  className="flex-1 text-sm text-gray-900 border border-gray-300 rounded-md px-3 py-1.5"
                />
                <button
                  onClick={handleCopyPermalink}
                  className="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  title="Copy permalink"
                >
                  {copiedPermalink ? (
                    <Check size={16} className="text-green-500" />
                  ) : (
                    <Copy size={16} />
                  )}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
