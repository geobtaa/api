import { appUrl } from '../api';
import { encodeId } from '../urlIds';
import { CompactActivity } from '../ui/CompactActivity';
import { ui } from '../ui/styles';
import {
  TextInput,
  SelectControl,
  ActionButton,
  DataTable,
} from '../ui/controls';
import { useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { Load, Pages } from '../sources/SourceBrowse';
import { setBase, type SetRecord, type SetContract, type Page } from './api';
export function SetList() {
  const [params, setParams] = useSearchParams();
  const q = params.get('q') ?? '';
  const source = params.get('source_id') ?? '';
  const status = params.get('status') ?? '';
  const offset = Math.max(0, Number(params.get('offset')) || 0);
  return (
    <main id="main-content" className={ui.page}>
      <h1>Sets</h1>
      <p className={ui.intro}>
        Source-owned groups with their own scope and acquisition context.
      </p>
      {source && (
        <p>
          Source: <Link to={`/sources/${encodeId(source)}`}>{source}</Link> ·{' '}
          <Link to="/sets">All Sets</Link>
        </p>
      )}
      <Load<SetContract> url={'/api/v1/admin/contracts/sets'}>
        {(contract) => (
          <>
            {contract.create && (
              <Link className={ui.primary} to={`/sets/new?${params}`}>
                Create Set
              </Link>
            )}
            {(contract.create || contract.update) && (
              <Link className={ui.secondary} to="/sets/csv/import">
                Import CSV
              </Link>
            )}
            <a
              className={ui.secondary}
              href={appUrl('/api/v1/admin/sets/csv/export')}
            >
              Export for editing
            </a>
            <form
              className={ui.search}
              role="search"
              onSubmit={(event) => {
                event.preventDefault();
                setParams({
                  ...(source ? { source_id: source } : {}),
                  status: String(
                    new FormData(event.currentTarget).get('status') ?? ''
                  ),
                  q: String(
                    new FormData(event.currentTarget).get('q') ?? ''
                  ).trim(),
                });
              }}
            >
              <label htmlFor="set-search">
                Search Sets by title, ID, or legacy code
              </label>
              <div className={ui.inline}>
                <TextInput
                  key={`search:${q}`}
                  defaultValue={q}
                  type="search"
                  name="q"
                  id="set-search"
                  maxLength={200}
                />
                <label htmlFor="set-state-filter">State</label>
                <SelectControl
                  key={`state:${status}`}
                  id="set-state-filter"
                  name="status"
                  defaultValue={status}
                >
                  <option value="">Active and inactive</option>
                  {(contract.states ?? ['active', 'inactive']).map((state) => (
                    <option key={state} value={state}>
                      {state}
                    </option>
                  ))}
                </SelectControl>
                <ActionButton className={ui.secondary}>Search</ActionButton>
              </div>
            </form>
            <Load<Page<SetRecord>>
              url={`${setBase}?${new URLSearchParams({ q, ...(status ? { status } : {}), offset: String(offset), limit: '25', ...(source ? { source_id: source } : {}) })}`}
            >
              {(page) => (
                <>
                  {page.items.length ? (
                    <div
                      className={ui.tableRegion}
                      role="region"
                      aria-label="Set results"
                      tabIndex={0}
                    >
                      <DataTable>
                        <thead>
                          <tr>
                            <th scope="col">Title / Set ID</th>
                            <th scope="col">Source</th>
                            <th scope="col">Legacy code</th>
                            <th scope="col">Status</th>
                            <th scope="col">Updated</th>
                          </tr>
                        </thead>
                        <tbody>
                          {page.items.map((item) => (
                            <tr key={item.set_id}>
                              <th scope="row">
                                <Link
                                  to={`/sets/${encodeId(item.set_id)}?${params}`}
                                >
                                  {item.title}
                                </Link>
                                <small className={ui.code}>{item.set_id}</small>
                              </th>
                              <td>
                                <Link
                                  to={`/sources/${encodeId(item.source_id)}`}
                                >
                                  {item.source_id}
                                </Link>
                              </td>
                              <td>{item.legacy_code || '—'}</td>
                              <td>{item.status}</td>
                              <td>
                                <time dateTime={item.updated_at}>
                                  {new Date(
                                    item.updated_at
                                  ).toLocaleDateString()}
                                </time>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </DataTable>
                    </div>
                  ) : (
                    <p>No Sets found. Try a different search.</p>
                  )}
                  <Pages
                    page={page}
                    label="Set pages"
                    change={(next) =>
                      setParams({
                        q,
                        ...(status ? { status } : {}),
                        offset: String(next),
                        ...(source ? { source_id: source } : {}),
                      })
                    }
                  />
                </>
              )}
            </Load>
          </>
        )}
      </Load>
    </main>
  );
}
export function SetHistory({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  type Entry = {
    id: string;
    action: string;
    outcome: string;
    actor_display_name: string;
    occurred_at: string;
    details: { fields?: string[] };
  };
  return (
    <section
      className="rounded-lg border border-border bg-surface p-4 shadow-xs"
      aria-labelledby="set-history"
    >
      <h2 id="set-history">Set history</h2>
      <Load<Page<Entry>>
        url={`${setBase}/${encodeURIComponent(id)}/activity?offset=${offset}&limit=20`}
      >
        {(page) => (
          <>
            {page.items.length ? (
              <CompactActivity entries={page.items} />
            ) : (
              <p>No Set history.</p>
            )}
            <Pages label="Set history pages" page={page} change={setOffset} />
          </>
        )}
      </Load>
    </section>
  );
}
