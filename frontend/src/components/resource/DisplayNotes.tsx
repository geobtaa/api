import React from 'react';
import { AlertTriangle, Flame, Info, Lightbulb } from 'lucide-react';
import { linkifyText } from '../../utils/linkifyText';

interface DisplayNotesProps {
  notes?: string[] | null;
}

type NoteVariant = 'danger' | 'info' | 'tip' | 'warning' | 'default';

interface NoteConfig {
  variant: NoteVariant;
  icon: React.ReactNode | null;
  classes: string;
}

const TIP_PREFIX = 'Tip: ';

const NOTE_PREFIXES: Array<{
  prefix: string;
  variant: Exclude<NoteVariant, 'default'>;
}> = [
  { prefix: 'Danger: ', variant: 'danger' },
  { prefix: 'Info: ', variant: 'info' },
  { prefix: 'Tip: ', variant: 'tip' },
  { prefix: 'Warning: ', variant: 'warning' },
];

function classifyNote(note: string): NoteConfig {
  const trimmed = note ?? '';

  for (const { prefix, variant } of NOTE_PREFIXES) {
    if (trimmed.startsWith(prefix)) {
      switch (variant) {
        case 'danger':
          return {
            variant,
            icon: <Flame className="h-4 w-4 text-red-600" aria-hidden="true" />,
            classes: 'border-red-200 bg-red-50 text-red-800',
          };
        case 'info':
          return {
            variant,
            icon: <Info className="h-4 w-4 text-blue-600" aria-hidden="true" />,
            classes: 'border-blue-200 bg-blue-50 text-blue-800',
          };
        case 'tip':
          return {
            variant,
            icon: (
              <Lightbulb
                className="h-4 w-4 text-emerald-600"
                aria-hidden="true"
              />
            ),
            classes: 'border-emerald-200 bg-emerald-50 text-emerald-800',
          };
        case 'warning':
          return {
            variant,
            icon: (
              <AlertTriangle
                className="h-4 w-4 text-amber-600"
                aria-hidden="true"
              />
            ),
            classes: 'border-amber-200 bg-amber-50 text-amber-800',
          };
      }
    }
  }

  // Default neutral style for non-prefixed notes
  return {
    variant: 'default',
    icon: null,
    classes: 'border-gray-200 bg-gray-50 text-gray-800',
  };
}

function getRenderedNoteText(note: string) {
  if (note.startsWith(TIP_PREFIX)) {
    return {
      text: note.slice(TIP_PREFIX.length).trimStart(),
      ariaLabel: note,
    };
  }

  return { text: note };
}

export function DisplayNotes({ notes }: DisplayNotesProps) {
  if (!notes || notes.length === 0) return null;

  return (
    <div
      className="space-y-3 mt-4 mb-4"
      aria-label="Important notes about this data resource"
    >
      {notes.map((note, index) => {
        if (!note || typeof note !== 'string') return null;

        const { icon, classes } = classifyNote(note);
        const { text, ariaLabel } = getRenderedNoteText(note);

        return (
          <div
            key={`${index}-${note.slice(0, 24)}`}
            className={`gbl-display-note flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${classes}`}
            role="status"
            aria-label={ariaLabel}
          >
            {icon && <div className="mt-0.5 shrink-0">{icon}</div>}
            <p className="leading-snug">{linkifyText(text)}</p>
          </div>
        );
      })}
    </div>
  );
}
