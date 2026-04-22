export const GALLERY_STATE_STORAGE_KEY = 'b1g_gallery_state';

const GALLERY_STATE_RESTORE_REQUEST_KEY = 'b1g_gallery_restore_requested';

export function requestGalleryStateRestore(): void {
  if (typeof window === 'undefined') return;

  try {
    window.sessionStorage.setItem(GALLERY_STATE_RESTORE_REQUEST_KEY, '1');
  } catch {
    // Ignore storage access issues.
  }
}

export function consumeGalleryStateRestoreRequest(): boolean {
  if (typeof window === 'undefined') return false;

  try {
    const requested =
      window.sessionStorage.getItem(GALLERY_STATE_RESTORE_REQUEST_KEY) === '1';
    window.sessionStorage.removeItem(GALLERY_STATE_RESTORE_REQUEST_KEY);
    return requested;
  } catch {
    return false;
  }
}
