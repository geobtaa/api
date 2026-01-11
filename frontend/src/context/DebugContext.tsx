import React, { createContext, useContext, useState } from 'react';

interface DebugContextType {
  showDetails: boolean;
  toggleDetails: () => void;
}

const DebugContext = createContext<DebugContextType | undefined>(undefined);

export function DebugProvider({ children }: { children: React.ReactNode }) {
  const [showDetails, setShowDetails] = useState(false);

  const toggleDetails = () => setShowDetails(!showDetails);

  return (
    <DebugContext.Provider value={{ showDetails, toggleDetails }}>
      {children}
    </DebugContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useDebug() {
  const context = useContext(DebugContext);
  if (context === undefined) {
    throw new Error('useDebug must be used within a DebugProvider');
  }
  return context;
}
