import type { ComponentProps } from 'react';
import { ui } from './styles';

export function TextInput({
  className = '',
  type = 'text',
  ...props
}: ComponentProps<'input'>) {
  const appearance =
    type === 'checkbox'
      ? 'form-checkbox size-4 shrink-0 rounded border-control text-active focus:ring-active disabled:cursor-not-allowed disabled:opacity-50'
      : type === 'radio'
        ? 'form-radio size-4 shrink-0 border-control text-active focus:ring-active disabled:cursor-not-allowed disabled:opacity-50'
        : type === 'file'
          ? `${ui.input} border file:mr-3 file:rounded-md file:border-0 file:bg-active-soft file:px-3 file:py-1 file:text-sm file:font-medium file:text-primary`
          : `form-input ${ui.input}`;
  return (
    <input {...props} type={type} className={`${appearance} ${className}`} />
  );
}

export function TextArea({
  className = '',
  ...props
}: ComponentProps<'textarea'>) {
  return (
    <textarea
      {...props}
      className={`form-textarea ${ui.input} min-h-32 resize-y ${className}`}
    />
  );
}

export function SelectControl({
  className = '',
  ...props
}: ComponentProps<'select'>) {
  return (
    <select
      {...props}
      className={`form-select ${ui.input} pr-9 ${className}`}
    />
  );
}

export function ActionButton({
  className = ui.secondary,
  ...props
}: ComponentProps<'button'>) {
  return <button {...props} className={className} />;
}

export function DataTable({
  className = '',
  ...props
}: ComponentProps<'table'>) {
  return <table {...props} className={`${ui.table} ${className}`} />;
}
