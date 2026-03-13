import React, { createContext, useCallback, useContext, useRef, useState } from 'react';

interface MapContextType {
  hoveredGeometry: string | null;
  setHoveredGeometry: (geometry: string | null) => void;
  hoveredResourceId: string | null;
  setHoveredResourceId: (id: string | null) => void;
  /** Only updates hoveredGeometry if user is still hovering this resource (avoids race with fetch) */
  setGeometryIfHovering: (resourceId: string, geometry: string | null) => void;
}

const MapContext = createContext<MapContextType | undefined>(undefined);

export function MapProvider({ children }: { children: React.ReactNode }) {
  const [hoveredGeometry, setHoveredGeometry] = useState<string | null>(null);
  const [hoveredResourceId, setHoveredResourceId] = useState<string | null>(
    null
  );
  const hoveredIdRef = useRef<string | null>(null);
  hoveredIdRef.current = hoveredResourceId;

  const setGeometryIfHovering = useCallback((resourceId: string, geometry: string | null) => {
    if (hoveredIdRef.current === resourceId) {
      setHoveredGeometry(geometry);
    }
  }, []);

  return (
    <MapContext.Provider
      value={{
        hoveredGeometry,
        setHoveredGeometry,
        hoveredResourceId,
        setHoveredResourceId,
        setGeometryIfHovering,
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
