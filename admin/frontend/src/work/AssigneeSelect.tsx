import { useEffect, useRef, useState } from 'react';
import { Load } from '../sources/SourceBrowse';
import { SelectControl } from '../ui/controls';
import { ui } from '../ui/styles';
import { taskBase, type Assignee } from './api';

export function AssigneeSelect({
  initial = null,
  setId,
  label = 'Assignee',
}: {
  initial?: string | null;
  setId: string;
  label?: string;
}) {
  const [value, setValue] = useState(initial ?? '');
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const form = input.current?.form;
    const reset = () => setValue(initial ?? '');
    form?.addEventListener('reset', reset);
    return () => form?.removeEventListener('reset', reset);
  }, [initial]);
  return (
    <>
      {/* Preserve the current assignment even while its choices are loading or unavailable. */}
      <input ref={input} type="hidden" name="assignee_id" value={value} />
      <Load<Assignee[]>
        url={`${taskBase}/assignees?limit=500${setId ? `&set_id=${encodeURIComponent(setId)}` : ''}`}
      >
        {(items) => (
          <label className={ui.field}>
            {label}
            <SelectControl
              value={value}
              onChange={(event) => setValue(event.target.value)}
            >
              <option value="">Unassigned</option>
              {value && !items.some((item) => item.actor_id === value) && (
                <option value={value}>
                  Current assignee (unavailable for new assignment)
                </option>
              )}
              {items.map((item) => (
                <option key={item.actor_id} value={item.actor_id}>
                  {item.display_name}
                </option>
              ))}
            </SelectControl>
          </label>
        )}
      </Load>
    </>
  );
}
