import React, { createContext, useContext, useState } from 'react';

interface MapContextType {
  hoveredGeometry: string | null;
  setHoveredGeometry: (geometry: string | null) => void;
  hoveredResourceId: string | null;
  setHoveredResourceId: (id: string | null) => void;
}

const MapContext = createContext<MapContextType | undefined>(undefined);

export function MapProvider({ children }: { children: React.ReactNode }) {
  const [hoveredGeometry, setHoveredGeometry] = useState<string | null>(null);
  const [hoveredResourceId, setHoveredResourceId] = useState<string | null>(
    null
  );

  return (
    <MapContext.Provider
      value={{
        hoveredGeometry,
        setHoveredGeometry,
        hoveredResourceId,
        setHoveredResourceId,
      }}
    >
      {children}
    </MapContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useMap() {
  const context = useContext(MapContext);
  if (context === undefined) {
    throw new Error('useMap must be used within a MapProvider');
  }
  return context;
}
