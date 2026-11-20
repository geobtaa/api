import { createContext } from 'react';

export const Drafts = createContext<{
  mark: (id: string) => void;
  clear: (id: string) => void;
  begin: (id: string) => void;
  end: (id: string) => void;
} | null>(null);
