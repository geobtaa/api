import yaml from 'js-yaml';

// Single source of truth for app configuration + theming.
// We load `theme.yaml` from the frontend package root as raw text (Vite `?raw`),
// then parse it at runtime in both server and browser bundles.
import themeYaml from '../../theme.yaml?raw';

export type ThemeId = string;

export interface ThemeConfig {
  label?: string;
  institution: {
    name: string;
    logo_url?: string;
    logo_lockup?: {
      separator?: 'pipe' | string;
      right_text?: string;
      right_text_style?: {
        font_family?: string;
        font_weight?: number;
        letter_spacing?: string;
      };
    };
    /**
     * Optional header-specific presentation config (keeps Header.tsx generic).
     * Values are in rem units.
     */
    header?: {
      logo_height_rem?: number;
      lockup_gap_rem?: number;
      lockup_separator_height_rem?: number;
      lockup_text_size_rem?: number;
    };
    hero_text?: string;
    hero_description?: string;
  };
  branding?: {
    colors?: {
      primary?: string;
      active?: string;
    };
    fonts?: {
      sans?: string;
    };
  };
  api: {
    base_url: string;
    search_path?: string;
    default_query_params?: string[];
    params?: {
      include_filters?: Record<string, string>;
    };
  };
  homepage?: {
    announcement?: {
      enabled?: boolean;
      text: string;
      link_label: string;
      link_url: string;
    };
    /** Optional resource IDs to show first in the featured carousel (e.g. ["uuid-1", "uuid-2"]). */
    featured_resource_ids?: string[];
    featured?: Array<{
      title: string;
      field: string;
      value: string;
      sort: string;
      limit: number;
    }>;
    blog?: {
      enabled?: boolean;
      title?: string;
      subtitle?: string;
      limit?: number;
      cta_label?: string;
      cta_url?: string;
      pinned_slugs?: string[];
    };
  };
}

export interface ThemeRegistryConfig {
  default_theme?: ThemeId;
  themes: Record<ThemeId, ThemeConfig>;
}

export const THEME_STORAGE_KEY = 'rui.theme';
export const THEME_COOKIE_KEY = 'rui.theme';
const THEME_CHANGED_EVENT = 'rui:theme-changed';

function parseThemeYaml(raw: string): ThemeRegistryConfig {
  const parsed = yaml.load(raw);
  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Invalid theme.yaml: expected an object at top-level');
  }
  const cfg = parsed as ThemeRegistryConfig;
  if (!cfg.themes || typeof cfg.themes !== 'object') {
    throw new Error('Invalid theme.yaml: expected `themes` map');
  }
  return cfg;
}

const registry = parseThemeYaml(themeYaml);

export function getThemeIds(): ThemeId[] {
  return Object.keys(registry.themes);
}

export function isKnownThemeId(themeId: string | null | undefined): boolean {
  return !!themeId && !!registry.themes[themeId];
}

export function getDefaultThemeId(): ThemeId {
  const ids = getThemeIds();
  return registry.default_theme && registry.themes[registry.default_theme]
    ? registry.default_theme
    : ids[0] || 'default';
}

export function getThemeConfig(themeId: ThemeId): ThemeConfig {
  return registry.themes[themeId] || registry.themes[getDefaultThemeId()];
}

export function getThemeLabel(themeId: ThemeId): string {
  const theme = getThemeConfig(themeId);
  return theme.label || theme.institution?.name || themeId;
}

export function getAvailableThemes(): Array<{ id: ThemeId; label: string }> {
  return getThemeIds().map((id) => ({ id, label: getThemeLabel(id) }));
}

function safeReadLocalStorage(key: string): string | null {
  try {
    return typeof window !== 'undefined'
      ? window.localStorage.getItem(key)
      : null;
  } catch {
    return null;
  }
}

function safeWriteLocalStorage(key: string, value: string): void {
  try {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // ignore
  }
}

function safeWriteCookie(key: string, value: string): void {
  try {
    if (typeof document === 'undefined') return;
    // 1 year
    document.cookie = `${encodeURIComponent(key)}=${encodeURIComponent(
      value
    )}; Path=/; Max-Age=31536000; SameSite=Lax`;
  } catch {
    // ignore
  }
}

export function getThemeIdFromCookieHeader(
  cookieHeader: string | null
): ThemeId | null {
  if (!cookieHeader) return null;
  const parts = cookieHeader.split(';').map((p) => p.trim());
  for (const part of parts) {
    const eq = part.indexOf('=');
    if (eq === -1) continue;
    const k = decodeURIComponent(part.slice(0, eq));
    if (k !== THEME_COOKIE_KEY) continue;
    const v = decodeURIComponent(part.slice(eq + 1));
    return isKnownThemeId(v) ? (v as ThemeId) : null;
  }
  return null;
}

export function getActiveThemeId(): ThemeId {
  // Browser-only: localStorage is the source of truth.
  const stored = safeReadLocalStorage(THEME_STORAGE_KEY);
  if (stored && isKnownThemeId(stored)) return stored;

  return getDefaultThemeId();
}

export function applyThemeToDom(themeId: ThemeId): void {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.theme = themeId;
}

export function setActiveThemeId(themeId: ThemeId): void {
  const next = isKnownThemeId(themeId) ? themeId : getDefaultThemeId();
  safeWriteLocalStorage(THEME_STORAGE_KEY, next);
  safeWriteCookie(THEME_COOKIE_KEY, next);
  applyThemeToDom(next);
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(THEME_CHANGED_EVENT, { detail: next })
    );
  }
}

export function subscribeToThemeChanges(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => {};
  const handler = () => callback();
  window.addEventListener(THEME_CHANGED_EVENT, handler as EventListener);
  return () =>
    window.removeEventListener(THEME_CHANGED_EVENT, handler as EventListener);
}

export function getActiveThemeConfig(): ThemeConfig {
  return getThemeConfig(getActiveThemeId());
}
