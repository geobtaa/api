import { useState, useEffect, useRef } from 'react';

const FACET_ACCORDION_STORAGE_KEY = 'b1g_facet_accordion';

export interface FacetAccordionState {
  opened: Set<string>;
  closed: Set<string>;
}

function loadAccordionFromStorage(): FacetAccordionState {
  if (typeof window === 'undefined') {
    return { opened: new Set(), closed: new Set() };
  }
  try {
    const raw = window.localStorage.getItem(FACET_ACCORDION_STORAGE_KEY);
    if (!raw) return { opened: new Set(), closed: new Set() };
    const parsed = JSON.parse(raw) as {
      opened?: string[];
      closed?: string[];
    };
    return {
      opened: new Set(parsed.opened ?? []),
      closed: new Set(parsed.closed ?? []),
    };
  } catch {
    return { opened: new Set(), closed: new Set() };
  }
}

function saveAccordionToStorage(accordion: FacetAccordionState): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(
      FACET_ACCORDION_STORAGE_KEY,
      JSON.stringify({
        opened: Array.from(accordion.opened),
        closed: Array.from(accordion.closed),
      })
    );
  } catch {
    // Ignore storage access issues
  }
}

export function useFacetAccordion() {
  // Initialize with empty to avoid SSR hydration mismatch; load from storage in useEffect
  const [accordion, setAccordion] = useState<FacetAccordionState>(() => ({
    opened: new Set(),
    closed: new Set(),
  }));
  const hasLoadedFromStorage = useRef(false);

  useEffect(() => {
    if (!hasLoadedFromStorage.current) {
      hasLoadedFromStorage.current = true;
      setAccordion(loadAccordionFromStorage());
      return;
    }
    saveAccordionToStorage(accordion);
  }, [accordion]);

  return { accordion, setAccordion };
}
