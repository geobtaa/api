import React from "react";
import { startTransition, StrictMode } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import "../src/config/fixLeafletDefaultIcon";

function removeInvalidDocumentElementChildren() {
  for (const child of Array.from(document.documentElement.children)) {
    const tagName = child.tagName.toLowerCase();
    if (tagName !== "head" && tagName !== "body") {
      child.remove();
    }
  }
}

startTransition(() => {
  removeInvalidDocumentElementChildren();

  hydrateRoot(
    document,
    <StrictMode>
      <HydratedRouter />
    </StrictMode>,
  );
});
