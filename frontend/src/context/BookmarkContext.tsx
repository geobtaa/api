import React, { createContext, useContext, useState, useEffect } from 'react';
import Cookies from 'js-cookie';

interface BookmarkContextType {
  bookmarks: string[];
  addBookmark: (id: string) => void;
  removeBookmark: (id: string) => void;
  isBookmarked: (id: string) => boolean;
}

const BookmarkContext = createContext<BookmarkContextType | undefined>(
  undefined
);

export function BookmarkProvider({ children }: { children: React.ReactNode }) {
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    const saved = Cookies.get('bookmarks');
    if (saved) {
      setBookmarks(JSON.parse(saved));
    }
    setIsInitialized(true);
  }, []);

  useEffect(() => {
    if (isInitialized) {
      Cookies.set('bookmarks', JSON.stringify(bookmarks));
    }
  }, [bookmarks, isInitialized]);

  const addBookmark = (id: string) => {
    setBookmarks((prev) => [...new Set([...prev, id])]);
  };

  const removeBookmark = (id: string) => {
    setBookmarks((prev) => prev.filter((bookmarkId) => bookmarkId !== id));
  };

  const isBookmarked = (id: string) => bookmarks.includes(id);

  return (
    <BookmarkContext.Provider
      value={{ bookmarks, addBookmark, removeBookmark, isBookmarked }}
    >
      {children}
    </BookmarkContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useBookmarks() {
  const context = useContext(BookmarkContext);
  if (context === undefined) {
    throw new Error('useBookmarks must be used within a BookmarkProvider');
  }
  return context;
}
