import { useEffect, useState } from 'react';
import { SelectControl } from '../ui/controls';
import { request } from '../sets/api';

type Option = {
  workflow_id: string;
  label: string;
  description: string;
  acquisition_mode: string;
};

export function WorkflowCatalogSelect({
  id,
  value,
  onChange,
  disabled,
  legacy,
}: {
  id: string;
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
  legacy?: string;
}) {
  const [options, setOptions] = useState<Option[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    request<Option[]>('/api/v1/admin/workflow-catalog')
      .then((items) => {
        if (active) {
          if (Array.isArray(items)) setOptions(items);
          else setError('Workflow choices are unavailable.');
        }
      })
      .catch(() => {
        if (active) setError('Workflow choices are unavailable.');
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <SelectControl
        id={id}
        value={value ?? ''}
        disabled={disabled || !!error}
        onChange={(event) => onChange(event.target.value || null)}
      >
        <option value="">No workflow selected</option>
        {options.map((option) => (
          <option key={option.workflow_id} value={option.workflow_id}>
            {option.label} ({option.workflow_id})
          </option>
        ))}
      </SelectControl>
      {legacy && !value && <small>Unmatched spreadsheet value: {legacy}</small>}
      {value && (
        <small>
          {options.find((option) => option.workflow_id === value)?.description}
        </small>
      )}
      {error && <small role="alert">{error}</small>}
    </>
  );
}
