import { Controller } from '@hotwired/stimulus';

/**
 * Minimal Stimulus controller to mount Mirador for a IIIF Presentation manifest.
 *
 * Usage:
 * <div data-controller="mirador-viewer"
 *      data-mirador-viewer-manifest-url-value="https://.../manifest.json"></div>
 */
export default class MiradorViewerController extends Controller {
  static values = {
    manifestUrl: String,
  };

  declare manifestUrlValue: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private instance: any | null = null;

  async connect() {
    const manifestId = this.manifestUrlValue;
    if (!manifestId) return;

    // Ensure the element has an id (Mirador wants an element id).
    if (!this.element.id) {
      this.element.id = 'mirador-viewer';
    }

    // GeoBlacklight-style: Mirador is loaded as a prebuilt UMD script (CDN) and exposed on window.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const Mirador = (globalThis as any).Mirador;
    if (!Mirador || typeof Mirador.viewer !== 'function') {
      // eslint-disable-next-line no-console
      console.error(
        'Mirador is not available on window. Ensure the Mirador CDN script loaded.'
      );
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const config: any = {
      id: this.element.id,
      windows: [
        {
          manifestId,
        },
      ],
      window: {
        allowFullscreen: true,
        allowClose: false,
        allowMaximize: false,
      },
      workspaceControlPanel: {
        enabled: false,
      },
    };

    // Mirador.viewer returns a viewer instance; store it for teardown.
    this.instance = Mirador.viewer(config);
  }

  disconnect() {
    // Best-effort cleanup; Mirador doesn't guarantee a stable destroy API across versions.
    if (this.instance && typeof this.instance.unmount === 'function') {
      this.instance.unmount();
    }
    this.instance = null;
  }
}
