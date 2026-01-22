import { startTransition, StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { HelmetProvider } from 'react-helmet-async';

startTransition(() => {
  hydrateRoot(
    document,
    <StrictMode>
      <HelmetProvider>
        <HydratedRouter />
      </HelmetProvider>
    </StrictMode>,
  );
});
