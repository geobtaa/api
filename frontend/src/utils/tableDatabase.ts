import * as duckdb from '@duckdb/duckdb-wasm';
import wasm from '@duckdb/duckdb-wasm/dist/duckdb-mvp.wasm?url';
import workerUrl from '@duckdb/duckdb-wasm/dist/duckdb-browser-mvp.worker.js?url';

export async function openTable(url: string, signal: AbortSignal) {
  const worker = new Worker(workerUrl);
  const db = new duckdb.AsyncDuckDB(new duckdb.VoidLogger(), worker);
  const stop = () => worker.terminate();
  signal.addEventListener('abort', stop, { once: true });
  try {
    if (signal.aborted) throw new Error('Cancelled');
    await db.instantiate(wasm);
    await db.open({
      maximumThreads: 1,
      filesystem: {
        reliableHeadRequests: true,
        allowFullHTTPReads: false,
        forceFullHTTPReads: false,
      },
    });
    await db.registerFileURL(
      'dataset.parquet',
      new URL(url, window.location.href).href,
      duckdb.DuckDBDataProtocol.HTTP,
      true
    );
    const connection = await db.connect();
    await connection.query("SET memory_limit='256MB'");
    return {
      connection,
      close: () => {
        signal.removeEventListener('abort', stop);
        stop();
      },
    };
  } catch (error) {
    signal.removeEventListener('abort', stop);
    stop();
    throw error;
  }
}
