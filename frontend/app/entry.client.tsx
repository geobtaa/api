import React from "react";
import { startTransition, StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { HelmetProvider } from 'react-helmet-async';
import "../src/config/fixLeafletDefaultIcon";

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
