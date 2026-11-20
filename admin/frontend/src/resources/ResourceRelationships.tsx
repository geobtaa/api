import { resourcePath, resourceApiPath } from '../urlIds';
import { ui } from '../ui/styles';
import { ActionButton, DataTable } from '../ui/controls';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { request, type Page } from '../sets/api';

type Relationship = {
  relationship: string;
  id: string;
  title: string | null;
  set_id: string | null;
};

export function ResourceRelationships({ id }: { id: string }) {
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [page, setPage] = useState<Page<Relationship> | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    request<Page<Relationship>>(
      `${resourceApiPath(id)}/relationships?${new URLSearchParams({ offset: String(offset) })}`
    )
      .then((value) => {
        if (active) setPage(value);
      })
      .catch(() => {
        if (active) setError(true);
      });
    return () => {
      active = false;
    };
  }, [id, offset, retry]);
  function navigate(next: number) {
    setPage(null);
    setError(false);
    setOffset(next);
  }
  return (
    <section
      className="border-b border-border p-4 sm:p-6 [&>p]:text-sm [&>p]:text-text-secondary"
      aria-labelledby="relationships-heading"
    >
      <h2 id="relationships-heading">Relationships</h2>
      <p>
        Saved relationships and links from other accessible Resources. Edit
        outgoing relationships in the fields below.
      </p>
      {error ? (
        <div role="alert">
          Relationships could not load.{' '}
          <ActionButton
            type="button"
            onClick={() => {
              setError(false);
              setRetry(retry + 1);
            }}
          >
            Retry
          </ActionButton>
        </div>
      ) : !page ? (
        <p role="status">Loading relationships…</p>
      ) : page.total === 0 ? (
        <p>No saved relationships.</p>
      ) : (
        <>
          <div
            className={ui.tableRegion}
            tabIndex={0}
            role="region"
            aria-label="Resource relationships"
          >
            <DataTable>
              <thead>
                <tr>
                  <th scope="col">Relationship</th>
                  <th scope="col">Resource</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((item) => (
                  <tr key={`${item.relationship}:${item.id}`}>
                    <td>{item.relationship}</td>
                    <td>
                      {item.title || item.set_id ? (
                        <>
                          <Link
                            to={
                              resourcePath(item.id) +
                              (item.set_id
                                ? '?' +
                                  new URLSearchParams({ set_id: item.set_id })
                                : '')
                            }
                          >
                            {item.title || item.id}
                          </Link>
                          <div className={ui.code}>{item.id}</div>
                        </>
                      ) : (
                        <>
                          <div className={ui.code}>{item.id}</div>
                          <span>Not available here</span>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </div>
          <nav className={ui.pagination} aria-label="Relationship pages">
            <ActionButton
              type="button"
              disabled={offset === 0}
              onClick={() => navigate(Math.max(0, offset - page.limit))}
            >
              Previous relationships
            </ActionButton>
            <span>
              {offset + 1}–{offset + page.items.length} of {page.total}
            </span>
            <ActionButton
              type="button"
              disabled={offset + page.limit >= page.total}
              onClick={() => navigate(offset + page.limit)}
            >
              Next relationships
            </ActionButton>
          </nav>
          <p>
            “Not available here” includes external identifiers, records not yet
            imported, and records outside your access.
          </p>
        </>
      )}
    </section>
  );
}
