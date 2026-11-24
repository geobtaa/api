import React from 'react';
import { Bookmark } from 'lucide-react';
import { useBookmarks } from '../context/BookmarkContext';

interface BookmarkButtonProps {
  itemId: string;
  resourceTitle?: string;
}

export function BookmarkButton({ itemId, resourceTitle }: BookmarkButtonProps) {
  const { isBookmarked, addBookmark, removeBookmark } = useBookmarks();
  const bookmarked = isBookmarked(itemId);

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault(); // Prevent triggering the parent link
    if (bookmarked) {
      removeBookmark(itemId);
    } else {
      addBookmark(itemId);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={`p-2 rounded-full hover:bg-gray-100 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 ${
        resourceTitle
          ? 'relative inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-1 text-sm font-medium text-blue-700'
          : bookmarked
            ? 'text-blue-500'
            : 'text-gray-400'
      }`}
      aria-label={
        resourceTitle
          ? `Bookmark ${resourceTitle}`
          : bookmarked
            ? 'Remove bookmark'
            : 'Add bookmark'
      }
      aria-pressed={resourceTitle ? bookmarked : undefined}
    >
      <Bookmark
        aria-hidden="true"
        className="w-5 h-5"
        fill={bookmarked ? 'currentColor' : 'none'}
      />
      {resourceTitle && (
        <span className="hidden [@container(min-width:28rem)]:inline">
          Bookmark
        </span>
      )}
    </button>
  );
}
