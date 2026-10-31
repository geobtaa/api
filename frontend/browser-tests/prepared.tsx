import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResourceViewer } from '../src/components/resource/ResourceViewer';
import '../src/index.css';
import type { PreviewDescription } from '../src/utils/preparedPreview';

type Row = {
  id: string;
  title: string;
  record?: Record<string, unknown>;
  manifest: PreviewDescription & {
    detail?: string;
    thumbnail_key?: string;
    coverage_key?: string;
    layers: (PreviewDescription['layers'][number] & { asset_key?: string })[];
  };
};

function Acceptance() {
  const [rows, setRows] = useState<Row[]>([]);
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState('');
  useEffect(() => {
    fetch('/pilot/report')
      .then((response) => {
        if (!response.ok)
          throw new Error('Start the local pilot evidence server first.');
        return response.json();
      })
      .then((results: Row[]) => setRows(results))
      .catch((failure: Error) => setError(failure.message));
  }, []);
  const row = rows[selected];
  return (
    <main className="p-6">
      <h1 className="text-xl font-bold mb-3">
        Application ResourceViewer — actual prepared assets
      </h1>
      {error && <p role="alert">{error}</p>}
      <select
        aria-label="Pilot resource"
        className="border p-2 mb-4 w-full"
        value={selected}
        onChange={(event) => setSelected(Number(event.target.value))}
      >
        {rows.map((item, index) => (
          <option value={index} key={item.id}>
            {item.title}
          </option>
        ))}
      </select>
      {row && (
        <p className="mb-3" role="status">
          {row.manifest.status}
          {row.manifest.detail ? ` — ${row.manifest.detail}` : ''}
        </p>
      )}
      {row && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 280px',
            gap: 16,
          }}
        >
          <ResourceViewer
            key={row.id}
            data={{
              id: row.id,
              attributes: {
                ogm: {
                  id: row.id,
                  dct_title_s: row.title,
                  gbl_resourceClass_sm: ['Datasets'],
                  gbl_mdVersion_s: 'Aardvark',
                  dct_accessRights_s: 'Public',
                  dct_references_s: '{}',
                  ...row.record,
                },
              },
              meta: {
                ui: {
                  preview: {
                    ...row.manifest,
                    layers: row.manifest.layers.map((layer) => ({
                      ...layer,
                      url: layer.asset_key
                        ? `${location.origin}/pilot/asset/${layer.asset_key}`
                        : layer.url,
                    })),
                  },
                },
              },
            }}
          />
          <aside>
            <p>
              {row.manifest.scope === 'sample'
                ? 'Representative member'
                : 'Dataset preview'}
            </p>
            {row.manifest.thumbnail_key ? (
              <img
                alt="Matching content thumbnail"
                src={`/pilot/asset/${row.manifest.thumbnail_key}`}
              />
            ) : (
              <p>Thumbnail withheld for review.</p>
            )}
            <p className="mt-4">Separate coverage map</p>
            {row.manifest.coverage_key && (
              <img
                alt="Coverage map"
                src={`/pilot/asset/${row.manifest.coverage_key}`}
              />
            )}
          </aside>
        </div>
      )}
    </main>
  );
}
createRoot(document.getElementById('root')!).render(<Acceptance />);
