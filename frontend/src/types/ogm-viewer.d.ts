import type React from 'react';

declare module 'ogm-viewer/components/p-BbMGvQFJ.js' {
  export function s(path: string): void;
}

declare module 'react' {
  namespace JSX {
    interface IntrinsicElements {
      'ogm-viewer': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement>,
        HTMLElement
      > & {
        theme?: 'light' | 'dark';
      };
    }
  }
}
