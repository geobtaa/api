import {
  getDefaultThemeId,
  getThemeConfig,
  getThemeIdFromCookieHeader,
  isKnownThemeId,
  type ThemeConfig,
  type ThemeId,
} from "../../src/config/institution";

export function getThemeIdFromRequest(request: Request): ThemeId {
  const url = new URL(request.url);
  const fromQuery = url.searchParams.get("theme");
  if (isKnownThemeId(fromQuery)) return fromQuery as ThemeId;

  const fromCookie = getThemeIdFromCookieHeader(request.headers.get("cookie"));
  if (fromCookie) return fromCookie;

  return getDefaultThemeId();
}

export function getThemeConfigFromRequest(request: Request): ThemeConfig {
  return getThemeConfig(getThemeIdFromRequest(request));
}

