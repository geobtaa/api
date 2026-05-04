const ENABLED_VALUES = new Set(['1', 'true', 'yes', 'on']);

function isEnabledValue(value: boolean | string | null | undefined): boolean {
  if (typeof value === 'boolean') return value;
  if (!value) return false;
  return ENABLED_VALUES.has(value.toLowerCase());
}

function isRuntimeDebugLoggingEnabled(): boolean {
  if (typeof window === 'undefined') return false;

  try {
    const params = new URLSearchParams(window.location.search);
    if (isEnabledValue(params.get('debug_logs'))) return true;

    return isEnabledValue(window.localStorage.getItem('btaa_debug_logs'));
  } catch {
    return false;
  }
}

export function isDebugLoggingEnabled(): boolean {
  return (
    import.meta.env.DEV ||
    isEnabledValue(import.meta.env.VITE_ENABLE_DEBUG_LOGS) ||
    isRuntimeDebugLoggingEnabled()
  );
}

export function debugLog(...args: unknown[]) {
  if (isDebugLoggingEnabled()) {
    console.log(...args);
  }
}

export function debugWarn(...args: unknown[]) {
  if (isDebugLoggingEnabled()) {
    console.warn(...args);
  }
}
