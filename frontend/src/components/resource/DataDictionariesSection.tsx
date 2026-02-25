import React, { Fragment } from 'react';

export interface DataDictionaryEntry {
  id: number;
  resource_data_dictionary_id: number;
  friendlier_id: string;
  field_name: string;
  field_type?: string | null;
  values?: string | null;
  definition?: string | null;
  definition_source?: string | null;
  parent_field_name?: string | null;
  position: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DataDictionary {
  id: number;
  friendlier_id: string;
  name?: string | null;
  description?: string | null;
  staff_notes?: string | null;
  tags: string;
  position: number;
  created_at?: string | null;
  updated_at?: string | null;
  entries: DataDictionaryEntry[];
}

interface DataDictionariesSectionProps {
  dictionaries: DataDictionary[];
  showContainer?: boolean;
}

function sortEntries(entries: DataDictionaryEntry[]): DataDictionaryEntry[] {
  return [...entries].sort((a, b) => {
    if (a.position !== b.position) return a.position - b.position;
    return a.id - b.id;
  });
}

export function DataDictionariesSection({
  dictionaries,
  showContainer = true,
}: DataDictionariesSectionProps) {
  if (!dictionaries.length) return null;

  const content = (
    <div className="px-6 pb-6 space-y-6">
      {dictionaries.map((dictionary) => {
        const sortedEntries = sortEntries(dictionary.entries ?? []);
        const entryByFieldName = new Map(
          sortedEntries.map((entry) => [entry.field_name, entry])
        );

        const rootEntries = sortedEntries.filter((entry) => {
          if (!entry.parent_field_name) return true;
          return !entryByFieldName.has(entry.parent_field_name);
        });

        const childrenByParent = new Map<string, DataDictionaryEntry[]>();
        sortedEntries.forEach((entry) => {
          if (!entry.parent_field_name) return;
          const list = childrenByParent.get(entry.parent_field_name) ?? [];
          list.push(entry);
          childrenByParent.set(entry.parent_field_name, list);
        });

        function renderEntryRows(
          entry: DataDictionaryEntry,
          depth: number
        ): React.ReactNode {
          const children = childrenByParent.get(entry.field_name) ?? [];
          return (
            <Fragment key={entry.id}>
              <tr className="hover:bg-gray-50 align-top">
                <td className="px-4 py-3 text-sm text-gray-900">
                  <div style={{ paddingLeft: `${depth * 1.25}rem` }}>
                    {depth > 0 ? <span className="mr-1 text-gray-400">↳</span> : null}
                    {entry.field_name}
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-gray-700">
                  {entry.field_type || '—'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-700">
                  {entry.values || '—'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-700">
                  {entry.definition || '—'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-700">
                  {entry.definition_source || '—'}
                </td>
              </tr>
              {children.map((child) => renderEntryRows(child, depth + 1))}
            </Fragment>
          );
        }

        return (
          <div key={dictionary.id}>
            <div className="mb-2">
              <h3 className="text-base font-semibold text-gray-900">
                {dictionary.name || 'Untitled Dictionary'}
              </h3>
              {dictionary.description ? (
                <p className="text-sm text-gray-600">{dictionary.description}</p>
              ) : null}
            </div>

            <div className="overflow-x-auto border border-gray-200 rounded-md">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Field Name
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Field Type
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Value(s)
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Definition
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Definition Source
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {rootEntries.length > 0 ? (
                    rootEntries.map((entry) => renderEntryRows(entry, 0))
                  ) : (
                    <tr>
                      <td
                        className="px-4 py-3 text-sm text-gray-500 italic"
                        colSpan={5}
                      >
                        No dictionary entries
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );

  if (!showContainer) {
    return content;
  }

  return (
    <section className="bg-white rounded-lg shadow-md overflow-hidden">
      <h2 className="text-lg font-semibold text-gray-900 px-6 py-4">
        Data Dictionary
      </h2>
      {content}
    </section>
  );
}
