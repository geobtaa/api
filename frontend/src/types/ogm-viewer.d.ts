import type React from 'react';

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
