import React from 'react';
import { createRoot } from 'react-dom/client';
import { ResourceViewer } from '../src/components/resource/ResourceViewer';
import '../src/index.css';
createRoot(document.getElementById('root')!).render(
  <main className="p-6">
    <h1 className="text-2xl">Tabular dataset — acceptance fixture</h1>
    <ResourceViewer
      data={{
        id: 'table',
        attributes: { ogm: {} },
        meta: {
          ui: {
            preview: {
              version: '1',
              status: 'ready',
              layers: [
                {
                  id: 'table',
                  name: 'Data table',
                  format: 'parquet',
                  url: '/fixtures/table.parquet',
                  row_count: 120000,
                  columns: [
                    { name: 'id', type: 'VARCHAR' },
                    { name: 'name', type: 'VARCHAR' },
                    { name: 'amount', type: 'BIGINT' },
                  ],
                },
              ],
            },
          },
        },
      }}
    />
  </main>
);
