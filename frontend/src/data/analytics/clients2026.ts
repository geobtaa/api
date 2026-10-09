export interface ClientUsage {
  name: string;
  channel: string;
  requests: number;
  searches: number;
  events: number;
}

export interface ClientSnapshot {
  clients: ClientUsage[];
  surfaces: { label: string; requests: number }[];
  recordedKeys: number | null;
  keyAttributedRequests: number;
  unattributedKeyRequests: number;
  qgisUserAgentRequests: number | null;
}

// Aggregate export September 9, 2026. No key values, hashes, or raw user agents.
export const clientSnapshots: Record<'2026-07' | '2026-08', ClientSnapshot> = {
  '2026-07': {
    clients: [
      {
        name: 'Not declared',
        channel: 'Not declared',
        requests: 612182,
        searches: 0,
        events: 0,
      },
      {
        name: 'geoportal-web',
        channel: 'browser',
        requests: 931,
        searches: 6457,
        events: 16824,
      },
      {
        name: 'codex-research-workbook',
        channel: 'script',
        requests: 18,
        searches: 0,
        events: 0,
      },
    ],
    surfaces: [
      {
        label: 'API documentation',
        requests: 265194,
      },
      {
        label: 'Access checks',
        requests: 229999,
      },
      {
        label: 'Other endpoints',
        requests: 61640,
      },
      {
        label: 'Analytics capture',
        requests: 25484,
      },
      {
        label: 'Resource API',
        requests: 24541,
      },
      {
        label: 'Search API',
        requests: 6229,
      },
      {
        label: 'OGC endpoints',
        requests: 44,
      },
      {
        label: 'MCP endpoints',
        requests: 0,
      },
    ],
    recordedKeys: 0,
    keyAttributedRequests: 0,
    unattributedKeyRequests: 613131,
    qgisUserAgentRequests: null,
  },
  '2026-08': {
    clients: [
      {
        name: 'Not declared',
        channel: 'Not declared',
        requests: 598091,
        searches: 0,
        events: 0,
      },
      {
        name: 'geoportal-web',
        channel: 'browser',
        requests: 644,
        searches: 7545,
        events: 21753,
      },
      {
        name: 'geoportal-ssr',
        channel: 'ssr',
        requests: 196,
        searches: 0,
        events: 0,
      },
    ],
    surfaces: [
      {
        label: 'API documentation',
        requests: 262565,
      },
      {
        label: 'Access checks',
        requests: 202957,
      },
      {
        label: 'Other endpoints',
        requests: 80537,
      },
      {
        label: 'Analytics capture',
        requests: 31337,
      },
      {
        label: 'Resource API',
        requests: 19948,
      },
      {
        label: 'Search API',
        requests: 1467,
      },
      {
        label: 'OGC endpoints',
        requests: 77,
      },
      {
        label: 'MCP endpoints',
        requests: 43,
      },
    ],
    recordedKeys: 0,
    keyAttributedRequests: 0,
    unattributedKeyRequests: 598931,
    qgisUserAgentRequests: 0,
  },
};

/** Combine disjoint months; unavailable evidence stays unavailable. */
export function combineClientSnapshots(
  snapshots: ClientSnapshot[]
): ClientSnapshot {
  const clients = new Map<string, ClientUsage>();
  const surfaces = new Map<string, number>();
  for (const snapshot of snapshots) {
    for (const row of snapshot.clients) {
      const key = JSON.stringify([row.name, row.channel]);
      const old = clients.get(key) ?? {
        ...row,
        requests: 0,
        searches: 0,
        events: 0,
      };
      clients.set(key, {
        ...row,
        requests: old.requests + row.requests,
        searches: old.searches + row.searches,
        events: old.events + row.events,
      });
    }
    for (const row of snapshot.surfaces)
      surfaces.set(row.label, (surfaces.get(row.label) ?? 0) + row.requests);
  }
  return {
    clients: [...clients.values()].sort((a, b) => b.requests - a.requests),
    surfaces: [...surfaces]
      .map(([label, requests]) => ({ label, requests }))
      .sort((a, b) => b.requests - a.requests),
    // Without key identities, nonzero monthly distinct counts cannot be combined.
    recordedKeys: snapshots.every((row) => row.recordedKeys === 0) ? 0 : null,
    keyAttributedRequests: snapshots.reduce(
      (n, row) => n + row.keyAttributedRequests,
      0
    ),
    unattributedKeyRequests: snapshots.reduce(
      (n, row) => n + row.unattributedKeyRequests,
      0
    ),
    qgisUserAgentRequests: snapshots.some(
      (row) => row.qgisUserAgentRequests === null
    )
      ? null
      : snapshots.reduce((n, row) => n + row.qgisUserAgentRequests!, 0),
  };
}
