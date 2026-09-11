import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  useState,
  type ReactElement,
  type ReactNode,
  type TableHTMLAttributes,
} from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

type NodeProps = {
  children?: ReactNode;
  'data-sort-value'?: string | number;
  'data-filter-value'?: string;
  'aria-hidden'?: boolean;
};
type Node = ReactElement<NodeProps>;
const elements = (children: ReactNode) =>
  Children.toArray(children).filter(isValidElement) as Node[];
const textOf = (node: ReactNode): string =>
  Children.toArray(node)
    .map((child): string => {
      if (typeof child === 'string' || typeof child === 'number')
        return String(child);
      if (isValidElement<NodeProps>(child))
        return child.props['aria-hidden']
          ? ''
          : (child.props['data-filter-value'] ?? textOf(child.props.children));
      return '';
    })
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
const collator = new Intl.Collator('en', {
  numeric: true,
  sensitivity: 'base',
});

function valueOf(cell: Node): number | string | null {
  const value = cell.props['data-sort-value'] ?? textOf(cell.props.children);
  if (typeof value === 'number') return value;
  const clean = value.trim().replace(/−/g, '-');
  if (/^(?:—|–|-|N\/A|Unavailable)?$/i.test(clean)) return null;
  const numeric = clean.replace(/[,\s]/g, '').replace(/%$/, '');
  return /^[+-]?\d+(?:\.\d+)?$/.test(numeric) ? Number(numeric) : clean;
}

/** Preserves semantic table markup, links, formatting and original ranking order. */
export function AnalyticsTable({
  children,
  label,
  ...props
}: TableHTMLAttributes<HTMLTableElement> & { label?: string }) {
  const id = useId();
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState<{
    column: number;
    direction: 'ascending' | 'descending';
  } | null>(null);
  const sections = elements(children);
  const caption = sections.find((section) => section.type === 'caption');
  const name = label ?? (textOf(caption?.props.children) || 'Report table');
  const body = sections.find((section) => section.type === 'tbody');
  const rows = elements(body?.props.children);
  const terms = filter.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  const visible = rows
    .map((row, index) => ({ row, index }))
    .filter(({ row }) => {
      const text = textOf(row.props.children).toLocaleLowerCase();
      return terms.every((term) => text.includes(term));
    });
  if (sort)
    visible.sort((a, b) => {
      const av = valueOf(elements(a.row.props.children)[sort.column]);
      const bv = valueOf(elements(b.row.props.children)[sort.column]);
      if (av === null || bv === null)
        return av === bv ? a.index - b.index : av === null ? 1 : -1;
      const compared =
        typeof av === 'number' && typeof bv === 'number'
          ? av - bv
          : collator.compare(String(av), String(bv));
      return (
        compared * (sort.direction === 'ascending' ? 1 : -1) ||
        a.index - b.index
      );
    });
  const head = sections.find((section) => section.type === 'thead');
  const columnCount = elements(
    elements(head?.props.children)[0]?.props.children
  ).length;
  return (
    <div className="analytics-data-table">
      <div className="analytics-table-tools">
        <label htmlFor={id}>
          Filter rows
          <input
            id={id}
            type="search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            aria-label={`Filter ${name}`}
            placeholder="Search this table…"
          />
        </label>
        <span role="status">
          {visible.length} of {rows.length} rows
        </span>
        <button
          type="button"
          disabled={!filter && !sort}
          onClick={() => {
            setFilter('');
            setSort(null);
          }}
        >
          Reset
        </button>
      </div>
      <table {...props}>
        {sections.map((section) => {
          if (section.type === 'thead')
            return cloneElement(
              section,
              {},
              elements(section.props.children).map((row) =>
                cloneElement(
                  row,
                  {},
                  elements(row.props.children).map((cell, column) => {
                    const active = sort?.column === column;
                    const direction = active ? sort.direction : 'none';
                    const Icon =
                      direction === 'ascending'
                        ? ArrowUp
                        : direction === 'descending'
                          ? ArrowDown
                          : ArrowUpDown;
                    return cloneElement(
                      cell as ReactElement<
                        TableHTMLAttributes<HTMLTableCellElement>
                      >,
                      { 'aria-sort': direction },
                      <button
                        type="button"
                        className="analytics-table-sort"
                        onClick={() =>
                          setSort({
                            column,
                            direction:
                              active && direction === 'ascending'
                                ? 'descending'
                                : 'ascending',
                          })
                        }
                      >
                        {cell.props.children}
                        <Icon size={14} aria-hidden="true" />
                      </button>
                    );
                  })
                )
              )
            );
          if (section.type === 'tbody')
            return cloneElement(
              section,
              {},
              visible.length ? (
                visible.map(({ row }) => row)
              ) : (
                <tr>
                  <td colSpan={columnCount}>
                    No matching rows. Clear the filter to see all records.
                  </td>
                </tr>
              )
            );
          return section;
        })}
      </table>
    </div>
  );
}
