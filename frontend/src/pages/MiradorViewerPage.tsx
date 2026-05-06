import { useEffect, useRef, useState } from 'react';

type MiradorConfig = {
  id: string;
  miradorDownloadPlugin: {
    restrictDownloadOnSizeDefinition: boolean;
  };
  window: {
    allowClose: boolean;
    allowFullscreen: boolean;
    allowMaximize: boolean;
    hideAnnotationsPanel: boolean;
    hideSearchPanel: boolean;
    hideWindowTitle: boolean;
  };
  windows: Array<{
    manifestId: string;
    thumbnailNavigationPosition: 'far-bottom';
  }>;
  workspace: {
    showZoomControls: boolean;
  };
  workspaceControlPanel: {
    enabled: boolean;
  };
};

type MiradorInstance = {
  destroy?: () => void;
  unmount?: () => void;
};

type MiradorViewer = (
  config: MiradorConfig,
  plugins?: unknown[]
) => MiradorInstance | void;

type MiradorNamespace = {
  viewer?: MiradorViewer;
};

type MiradorModule = MiradorNamespace & {
  default?: MiradorNamespace;
};

type MiradorDownloadPluginModule = {
  default?: unknown[];
};

const MIRADOR_ROOT_ID = 'mirador-root';

function getManifestUrl() {
  if (typeof window === 'undefined') return '';
  return new URL(window.location.href).searchParams.get('manifest') ?? '';
}

function getViewer(module: MiradorModule) {
  return module.default?.viewer ?? module.viewer;
}

export function MiradorViewerPage() {
  const instanceRef = useRef<MiradorInstance | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const manifestUrl = getManifestUrl();
    if (!manifestUrl) {
      setError('Missing IIIF manifest URL.');
      return;
    }

    let cancelled = false;

    async function boot() {
      const [miradorModule, downloadPluginModule] = await Promise.all([
        import('mirador') as Promise<MiradorModule>,
        import('mirador-dl-plugin') as Promise<MiradorDownloadPluginModule>,
      ]);

      if (cancelled) return;

      const viewer = getViewer(miradorModule);
      if (!viewer) {
        throw new Error('Mirador viewer export was not found.');
      }

      const downloadPlugins = Array.isArray(downloadPluginModule.default)
        ? downloadPluginModule.default
        : [];

      instanceRef.current =
        viewer(
          {
            id: MIRADOR_ROOT_ID,
            miradorDownloadPlugin: {
              restrictDownloadOnSizeDefinition: true,
            },
            windows: [
              {
                manifestId: manifestUrl,
                thumbnailNavigationPosition: 'far-bottom',
              },
            ],
            window: {
              hideSearchPanel: false,
              hideWindowTitle: true,
              hideAnnotationsPanel: true,
              allowClose: false,
              allowMaximize: false,
              allowFullscreen: true,
            },
            workspace: { showZoomControls: true },
            workspaceControlPanel: { enabled: false },
          },
          [...downloadPlugins]
        ) ?? null;
    }

    boot().catch((err) => {
      const message =
        err instanceof Error ? err.message : 'Mirador failed to load.';
      setError(message);
      console.error('Mirador failed to load:', err);
    });

    return () => {
      cancelled = true;
      instanceRef.current?.unmount?.();
      instanceRef.current?.destroy?.();
      instanceRef.current = null;
    };
  }, []);

  return (
    <main className="h-screen w-screen bg-white">
      <div id={MIRADOR_ROOT_ID} className="h-screen w-screen" />
      {error && (
        <div
          role="alert"
          className="absolute inset-0 flex items-center justify-center bg-white p-6 text-center text-sm text-red-700"
        >
          {error}
        </div>
      )}
    </main>
  );
}
