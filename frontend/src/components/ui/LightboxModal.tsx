import { useEffect, useRef, MouseEvent } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export interface LightboxModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** ID for the dialog element (for aria-controls on trigger) */
  id?: string;
  /** ID of the element that labels the dialog (e.g. heading) */
  labelledBy: string;
  /** Optional ID for extended description */
  describedBy?: string;
  title: string;
  /** Optional subtitle/description below the title */
  subtitle?: string;
  children: React.ReactNode;
  /** Extra class for the content box */
  contentClassName?: string;
  /** Test id for the overlay */
  'data-testid'?: string;
}

/**
 * Shared lightbox modal: full-screen overlay, centered content, Escape/click-outside to close.
 * Use for facet "More" modal, hex table modal, and other dialogs.
 * Provides: focus management, focus trap, role="dialog", aria-modal.
 */
export function LightboxModal({
  isOpen,
  onClose,
  id,
  labelledBy,
  describedBy,
  title,
  subtitle,
  children,
  contentClassName = '',
  'data-testid': dataTestId = 'lightbox-modal-overlay',
}: LightboxModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previousActiveElement = useRef<Element | null>(null);
  const previousBodyOverflow = useRef<string>('');

  // Disable body scroll when modal is open
  useEffect(() => {
    if (!isOpen) return;
    previousBodyOverflow.current = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousBodyOverflow.current;
    };
  }, [isOpen]);

  // Focus management: trap and return
  useEffect(() => {
    if (!isOpen) return;

    previousActiveElement.current = document.activeElement;
    closeButtonRef.current?.focus();

    const content = contentRef.current;
    if (!content) return;

    const focusableSelector =
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    const focusables = content.querySelectorAll<HTMLElement>(focusableSelector);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }

      // Focus trap: Tab cycles within modal
      if (e.key !== 'Tab') return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus();
      }
    };
  }, [isOpen, onClose]);

  const handleOverlayMouseDown = (e: MouseEvent<HTMLDivElement>) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  // Portal to document.body so the modal escapes map/parent stacking contexts
  // and reliably appears above Search Form, carousel, and featured popup (z-20).
  const modalContent = (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-[10050] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onMouseDown={handleOverlayMouseDown}
      data-testid={dataTestId}
    >
      <div
        ref={contentRef}
        id={id}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        className={`bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col ${contentClassName}`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50 shrink-0">
          <div>
            <h2 id={labelledBy} className="text-lg font-semibold text-gray-900">
              {title}
            </h2>
            {subtitle && (
              <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
            )}
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded"
            aria-label="Close modal"
          >
            <X className="h-6 w-6" />
          </button>
        </header>
        {children}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
