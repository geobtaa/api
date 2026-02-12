import React from 'react';
import { ExternalLink } from 'lucide-react';

const URL_REGEX = /(https?:\/\/[^\s]+)/g;

/** Strip trailing punctuation that is usually sentence punctuation, not part of the URL. */
function trimTrailingPunctuation(url: string): string {
  return url.replace(/[)\]\}"']+$/, '');
}

/** Convert any URLs in a string into clickable external links (opens in new tab). */
export function linkifyText(text: string): React.ReactNode {
  if (!text) return '';

  const segments: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  // Reset lastIndex in case regex was used elsewhere
  URL_REGEX.lastIndex = 0;

  // Find URLs and split text around them
  // eslint-disable-next-line no-cond-assign
  while ((match = URL_REGEX.exec(text)) !== null) {
    const rawUrl = match[0];
    const url = trimTrailingPunctuation(rawUrl);
    const start = match.index;

    // Text before the URL
    if (start > lastIndex) {
      segments.push(text.slice(lastIndex, start));
    }

    // URL itself:
    // - href is trimmed so the link works
    // - visible text is the trimmed URL
    // - any trailing punctuation (like a closing parenthesis) remains outside the link
    segments.push(
      <a
        key={`url-${start}-${url}`}
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-blue-800 hover:text-blue-900"
      >
        <span>{url}</span>
        <ExternalLink className="h-3 w-3" aria-hidden="true" />
      </a>
    );

    // Advance only by the trimmed URL length so trailing punctuation is rendered after the link
    lastIndex = start + url.length;
  }

  // Trailing text after the last URL
  if (lastIndex < text.length) {
    segments.push(text.slice(lastIndex));
  }

  // If no URLs were found, just return the original string
  if (segments.length === 0) {
    return text;
  }

  return segments;
}
