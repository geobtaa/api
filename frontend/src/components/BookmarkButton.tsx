import React from 'react';
import { Bookmark } from 'lucide-react';
import { useBookmarks } from '../context/BookmarkContext';

interface BookmarkButtonProps {
  itemId: string;
}

export function BookmarkButton({ itemId }: BookmarkButtonProps) {
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
      onClick={handleClick}
      className={`p-2 rounded-full hover:bg-gray-100 transition-colors ${
        bookmarked ? 'text-blue-500' : 'text-gray-400'
      }`}
      aria-label={bookmarked ? 'Remove bookmark' : 'Add bookmark'}
    >
      <Bookmark
        className="w-5 h-5"
        fill={bookmarked ? 'currentColor' : 'none'}
      />
    </button>
  );
}
