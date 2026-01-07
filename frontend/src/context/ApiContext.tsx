import React, { createContext, useContext, useState } from 'react';

interface ApiContextType {
  lastApiUrl: string | null;
  setLastApiUrl: (url: string) => void;
}

const ApiContext = createContext<ApiContextType | null>(null);

export function ApiProvider({ children }: { children: React.ReactNode }) {
  const [lastApiUrl, setLastApiUrl] = useState<string | null>(null);

  return (
    <ApiContext.Provider value={{ lastApiUrl, setLastApiUrl }}>
      {children}
    </ApiContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useApi() {
  const context = useContext(ApiContext);
  if (!context) {
    // Be resilient: don't crash render if the provider tree differs (SSR, error boundaries, etc.).
    // This keeps the app usable even if the debug provider wiring is temporarily missing.
    return {
      lastApiUrl: null,
      setLastApiUrl: () => {},
    } as ApiContextType;
  }
  return context;
}
