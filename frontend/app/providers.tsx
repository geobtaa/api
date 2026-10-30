import React from 'react';
import { ApiProvider } from '../src/context/ApiContext';
import { BookmarkProvider } from '../src/context/BookmarkContext';
import { DebugProvider } from '../src/context/DebugContext';
import { MapProvider } from '../src/context/MapContext';
import { ThemeProvider } from '../src/context/ThemeContext';
import type { ThemeId } from '../src/config/institution';
import { TurnstileGate } from '../src/components/security/TurnstileGate';

export function Providers({
  children,
  initialThemeId,
  turnstilePreview = false,
}: {
  children: React.ReactNode;
  initialThemeId?: ThemeId;
  turnstilePreview?: boolean;
}) {
  return (
    <ThemeProvider initialThemeId={initialThemeId}>
      <TurnstileGate devPreview={turnstilePreview}>
        <ApiProvider>
          <BookmarkProvider>
            <DebugProvider>
              <MapProvider>{children}</MapProvider>
            </DebugProvider>
          </BookmarkProvider>
        </ApiProvider>
      </TurnstileGate>
    </ThemeProvider>
  );
}
