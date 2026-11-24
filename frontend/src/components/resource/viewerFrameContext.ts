import { createContext } from 'react';
import type { PreviewTab } from 'ogm-viewer/lib';

/** Available height is supplied by the expanded viewer frame, below its toolbar. */
export const ViewerExpandedContext = createContext(false);

export interface ViewerPreviewTabs {
  tabs: PreviewTab[];
  select: (id: string) => void;
}

export const ViewerTabsContext = createContext<
  ((navigation: ViewerPreviewTabs | null) => void) | null
>(null);
