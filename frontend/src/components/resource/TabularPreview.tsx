import { useEffect, useState } from 'react';
import type { PreparedLayer } from '../../utils/preparedPreview';
import { tableQuery } from '../../utils/tableQuery';

export default function TabularPreview({
  layers,
}: {
  layers: PreparedLayer[];
}) {
  const [index, setIndex] = useState(0);
  const layer = layers[index] ?? layers[0];
  return (
    <section aria-label="Dataset table" className="p-4">
      {layers.length > 1 && (
        <label>
          Table{' '}
          <select
            value={index}
            onChange={(event) => setIndex(Number(event.target.value))}
          >
            {layers.map((item, i) => (
              <option key={item.id} value={i}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <Table key={layer.url} layer={layer} />
    </section>
  );
}

function Table({ layer }: { layer: PreparedLayer }) {
  const columns = (layer.columns ?? []).map((column) => column.name);
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState(-1);
  const [descending, setDescending] = useState(false);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState('Loading table…');
  const [retry, setRetry] = useState(0);
  const [cancel, setCancel] = useState<() => void>(() => () => {});
  const columnKey = JSON.stringify(columns);
  useEffect(() => {
    const controller = new AbortController();
    let close = () => {};
    const fail = (message: string) => {
      controller.abort();
      close();
      setRows([]);
      setStatus(message);
    };
    setCancel(() => () => fail('Table query cancelled. Retry to continue.'));
    setStatus('Loading table…');
    const timer = window.setTimeout(
      () =>
        fail(
          'Table query exceeded 30 seconds. Try a smaller dataset or retry.'
        ),
      30000
    );
    void (async () => {
      try {
        const { openTable } = await import('../../utils/tableDatabase');
        if (controller.signal.aborted) return;
        const session = await openTable(layer.url, controller.signal);
        close = session.close;
        const query = tableQuery(
          JSON.parse(columnKey),
          search,
          page,
          sort,
          descending
        );
        const result = await session.connection.query(query.rows);
        const total = await session.connection.query(query.count);
        if (!controller.signal.aborted) {
          setRows(result.toArray().map((row) => row.toJSON()));
          setCount(Number(total.get(0)?.count ?? 0));
          setStatus('');
        }
      } catch {
        if (!controller.signal.aborted)
          setStatus(
            'Table preview unavailable. Retry or use the original download.'
          );
      } finally {
        window.clearTimeout(timer);
        close();
      }
    })();
    return () => {
      window.clearTimeout(timer);
      controller.abort();
      close();
    };
  }, [layer.url, columnKey, search, page, sort, descending, retry]);
  return (
    <>
      <form
        className="flex gap-2 mb-3"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(0);
          setSearch(input);
        }}
      >
        <label>
          Search this dataset{' '}
          <input
            className="border rounded px-2 py-1"
            type="search"
            value={input}
            maxLength={200}
            onChange={(event) => setInput(event.target.value)}
          />
        </label>
        <button className="border rounded px-3" type="submit">
          Search
        </button>
      </form>
      <p className="text-sm mb-2">
        Search matches text across all columns. Sorting uses the stored column
        types. Original downloads remain available.
      </p>
      {status ? (
        <div role="status">
          {status} <button onClick={() => setRetry(retry + 1)}>Retry</button>{' '}
          {status === 'Loading table…' && (
            <button onClick={cancel}>Cancel</button>
          )}
        </div>
      ) : (
        <>
          <p role="status">
            {count.toLocaleString()} matching rows ·{' '}
            {layer.row_count?.toLocaleString()} total rows
          </p>
          <div
            className="overflow-auto max-h-[480px]"
            tabIndex={0}
            aria-label="Scrollable data table"
          >
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr>
                  {columns.map((name, i) => (
                    <th
                      key={name}
                      scope="col"
                      aria-sort={
                        sort === i
                          ? descending
                            ? 'descending'
                            : 'ascending'
                          : 'none'
                      }
                      className="text-left border p-2"
                    >
                      <button
                        onClick={() => {
                          setSort(i);
                          setDescending(sort === i ? !descending : false);
                          setPage(0);
                        }}
                      >
                        {name}
                        {sort === i ? (descending ? ' ↓' : ' ↑') : ''}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i}>
                    {columns.map((name) => (
                      <td key={name} className="border p-2 whitespace-pre-wrap">
                        {row[name] == null ? (
                          <span aria-label="Null value">—</span>
                        ) : (
                          String(row[name])
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-3 mt-3">
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <span>
              Page {page + 1} of {Math.max(1, Math.ceil(count / 50))}
            </span>
            <button
              disabled={(page + 1) * 50 >= count}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </>
  );
}
