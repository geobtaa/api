import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useSyncExternalStore } from 'react';
import {
  applyThemeToDom,
  getActiveThemeId,
  getDefaultThemeId,
  getThemeConfig,
  subscribeToThemeChanges,
  type ThemeConfig,
  type ThemeId,
} from '../config/institution';

export interface ThemeContextValue {
  themeId: ThemeId;
  theme: ThemeConfig;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({
  children,
  initialThemeId,
}: {
  children: React.ReactNode;
  /**
   * Theme id used for SSR HTML + the client's first render, so hydration matches.
   * After mount, we reconcile with localStorage (if present) to respect user choice.
   */
  initialThemeId?: ThemeId;
}) {
  const initial = initialThemeId || getDefaultThemeId();
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);

  const themeId = useSyncExternalStore(
    subscribeToThemeChanges,
    () => (hydrated ? getActiveThemeId() : initial),
    () => initial
  );

  // Ensure the DOM reflects the current theme even on first load.
  // Use useEffect (not useLayoutEffect) so SSR doesn't warn; theme is already set
  // on <html data-theme> from the server, so this just syncs client state.
  useEffect(() => {
    applyThemeToDom(themeId);
  }, [themeId]);

  const theme = useMemo<ThemeConfig>(() => getThemeConfig(themeId), [themeId]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      themeId,
      theme,
    }),
    [themeId, theme]
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useThemeContext(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx) return ctx;

  // Safe fallback for tests or non-provider renders (keeps components from hard-crashing).
  const fallbackId = getDefaultThemeId();
  return {
    themeId: fallbackId,
    theme: getThemeConfig(fallbackId),
  };
}
