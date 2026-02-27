const HEX_LAYER_ENABLED_STORAGE_KEY = 'hex_layer_enabled';

export function getSavedHexLayerEnabled(): boolean {
  if (typeof window === 'undefined') return true;

  try {
    const saved = window.localStorage.getItem(HEX_LAYER_ENABLED_STORAGE_KEY);
    if (saved === null) return true;
    if (saved === '1' || saved === 'true') return true;
    if (saved === '0' || saved === 'false') return false;
  } catch {
    // Ignore storage access issues and fall back to default.
  }

  return true;
}

export function saveHexLayerEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(
      HEX_LAYER_ENABLED_STORAGE_KEY,
      enabled ? '1' : '0'
    );
  } catch {
    // Ignore storage access issues.
  }
}
