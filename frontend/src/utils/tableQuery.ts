/** Only identifiers from the published schema and escaped literals enter SQL. */
export const sqlIdentifier = (value: string) =>
  `"${value.replaceAll('"', '""')}"`;
export const sqlLiteral = (value: string) => `'${value.replaceAll("'", "''")}'`;
export function tableQuery(
  columns: string[],
  search: string,
  page: number,
  sort: number,
  descending: boolean
) {
  const filter = search
    ? ` WHERE ${columns.map((name) => `contains(lower(COALESCE(CAST(${sqlIdentifier(name)} AS VARCHAR), '')), lower(${sqlLiteral(search)}))`).join(' OR ')}`
    : '';
  const order = columns[sort]
    ? ` ORDER BY data.${sqlIdentifier(columns[sort])} ${descending ? 'DESC' : 'ASC'} NULLS LAST`
    : '';
  return {
    rows: `SELECT ${columns.map((name) => `CAST(${sqlIdentifier(name)} AS VARCHAR) AS ${sqlIdentifier(name)}`).join(', ')} FROM read_parquet('dataset.parquet') AS data${filter}${order} LIMIT 50 OFFSET ${Math.max(0, Math.floor(page)) * 50}`,
    count: `SELECT count(*) AS count FROM read_parquet('dataset.parquet') AS data${filter}`,
  };
}
