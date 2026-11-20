import { ui } from './ui/styles';
import { TextInput, ActionButton, DataTable } from './ui/controls';
import { useEffect, useState } from 'react';
import { request } from './sets/api';

type Fixture = {
  filename: string;
  purpose: string;
  metadata: Record<string, unknown>;
};
type Catalog = { source_commit: string; items: Fixture[] };

function value(metadata: Fixture['metadata'], field: string) {
  const v = metadata[field];
  return Array.isArray(v) ? v.join(', ') : String(v ?? 'Not supplied');
}

export function ResourceFixtures() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [query, setQuery] = useState('');
  useEffect(() => {
    let active = true;
    request<Catalog>('/api/v1/admin/resource-fixtures')
      .then((data) => {
        if (active) setCatalog(data);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [retry]);
  const items = catalog?.items.filter(({ metadata }) =>
    ['id', 'dct_title_s', 'schema_provider_s', 'gbl_resourceClass_sm'].some(
      (field) =>
        value(metadata, field)
          .toLowerCase()
          .includes(query.trim().toLowerCase())
    )
  );
  return (
    <main id="main-content" className={ui.page}>
      <p className={ui.kicker}>Development collection</p>
      <h1>Resource fixtures</h1>
      <p className={ui.intro}>
        Sample metadata from the Geoportal. Preview these records as we build
        Resource management.
      </p>
      <p className={ui.notice}>
        Fixtures are read-only examples, not saved application Resources.
        Original publication and access labels describe the source fixture.
      </p>
      {error ? (
        <div role="alert" className={ui.notice}>
          <p>
            Could not load fixtures. This catalog requires a development
            environment and access to the admin session.
          </p>
          <ActionButton
            className={ui.secondary}
            onClick={() => {
              setError(false);
              setRetry(retry + 1);
            }}
          >
            Retry
          </ActionButton>
        </div>
      ) : !catalog ? (
        <p role="status">Loading fixtures…</p>
      ) : (
        <>
          <div className={ui.search}>
            <label htmlFor="fixture-search">
              Search title, ID, provider, or class
            </label>
            <TextInput
              id="fixture-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <p role="status">
            {items!.length} of {catalog.items.length} fixtures
          </p>
          <div
            className={ui.tableRegion}
            role="region"
            aria-label="Resource fixtures"
            tabIndex={0}
          >
            <DataTable>
              <caption className="sr-only">
                Geoportal starter collection
              </caption>
              <thead>
                <tr>
                  <th scope="col">Resource</th>
                  <th scope="col">Class / provider</th>
                  <th scope="col">Source status</th>
                  <th scope="col">Metadata</th>
                </tr>
              </thead>
              <tbody>
                {items!.map((item) => (
                  <tr key={item.filename}>
                    <th scope="row">
                      {value(item.metadata, 'dct_title_s')}
                      <span className={ui.code}>
                        {value(item.metadata, 'id')}
                      </span>
                    </th>
                    <td>
                      {value(item.metadata, 'gbl_resourceClass_sm')}
                      <p>{value(item.metadata, 'schema_provider_s')}</p>
                    </td>
                    <td>
                      {value(item.metadata, 'b1g_publication_state_s')}
                      <p>{value(item.metadata, 'dct_accessRights_s')}</p>
                      {item.metadata.gbl_suppressed_b === true && (
                        <strong>Suppressed</strong>
                      )}
                    </td>
                    <td>
                      <details>
                        <summary>Inspect JSON</summary>
                        <p>{item.purpose}</p>
                        <p>{item.filename}</p>
                        <pre className="max-w-xl whitespace-pre-wrap text-xs [overflow-wrap:anywhere]">
                          {JSON.stringify(item.metadata, null, 2)}
                        </pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          {items!.length === 0 && <p>No fixtures match your search.</p>}
        </>
      )}
    </main>
  );
}
