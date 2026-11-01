import { describe, expect, it } from 'vitest';
import { tableQuery } from '../../utils/tableQuery';
import { readyTableLayers } from '../../utils/preparedPreview';

describe('dataset table queries', () => {
  it('escapes literal searches and schema identifiers', () => {
    const result = tableQuery(['a"b'], "' OR true --", 1, 0, true);
    expect(result.rows).toContain('"a""b"');
    expect(result.rows).toContain("lower(''' OR true --')");
    expect(result.rows).toContain('DESC NULLS LAST LIMIT 50 OFFSET 50');
    expect(result.count).not.toContain('LIMIT');
  });
  it('requires a ready versioned manifest and a schema', () => {
    const preview = {
      version: '1',
      status: 'ready',
      layers: [
        {
          id: 'table',
          name: 'table',
          format: 'parquet',
          url: '/table.parquet',
          columns: [{ name: 'id', type: 'VARCHAR' }],
        },
      ],
    };
    expect(readyTableLayers({ meta: { ui: { preview } } })).toHaveLength(1);
    expect(
      readyTableLayers({
        meta: { ui: { preview: { ...preview, status: 'invalid' } } },
      })
    ).toHaveLength(0);
    expect(
      readyTableLayers({
        meta: { ui: { preview: { ...preview, version: '2' } } },
      })
    ).toHaveLength(0);
  });
});
