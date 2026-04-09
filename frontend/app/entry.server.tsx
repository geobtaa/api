import { PassThrough, Transform } from "node:stream";

import type { AppLoadContext, EntryContext } from "react-router";
import { createReadableStreamFromReadable } from "@react-router/node";
import { ServerRouter } from "react-router";
import { isbot } from "isbot";
import type { RenderToPipeableStreamOptions } from "react-dom/server";
import { renderToPipeableStream } from "react-dom/server";
import { HelmetProvider } from 'react-helmet-async';
import { buildXRobotsTag } from "./lib/search-engine-indexing.server";

export const streamTimeout = 5_000;

/**
 * Transform stream that injects react-helmet-async tags into the HTML head.
 * Buffers HTML chunks until we can inject helmet tags into the <head> section.
 */
function createHelmetInjector(helmetContext: any) {
  let buffer = '';
  let headInjected = false;
  const MAX_BUFFER_SIZE = 200000; // 200KB safety limit

  return new Transform({
    transform(chunk: Buffer, encoding, callback) {
      const chunkStr = chunk.toString('utf-8');
      buffer += chunkStr;

      // Check for helmet data in context
      const helmetData = helmetContext.helmet;

      // If we have helmet data and haven't injected yet, look for </head> tag
      if (helmetData && !headInjected) {
        const headCloseIndex = buffer.indexOf('</head>');
        if (headCloseIndex !== -1) {
          // Extract helmet tags as HTML strings
          const helmetHtml = [
            helmetData.title?.toString() || '',
            helmetData.meta?.toString() || '',
            helmetData.link?.toString() || '',
            helmetData.script?.toString() || '',
            helmetData.style?.toString() || '',
            helmetData.noscript?.toString() || '',
          ]
            .filter(Boolean)
            .join('\n    ');

          // Inject helmet tags before </head>
          const beforeHead = buffer.substring(0, headCloseIndex);
          const afterHead = buffer.substring(headCloseIndex);
          buffer = beforeHead + '\n    ' + helmetHtml + '\n  ' + afterHead;
          headInjected = true;
        }
      }

      // Safety: if buffer gets too large, pass it through even if we haven't injected
      if (buffer.length > MAX_BUFFER_SIZE) {
        this.push(Buffer.from(buffer, 'utf-8'));
        buffer = '';
        callback();
        return;
      }

      // If we've injected the helmet tags, we can start streaming
      // But we still need to buffer a bit to ensure we got the head section
      if (headInjected) {
        this.push(Buffer.from(buffer, 'utf-8'));
        buffer = '';
      }

      callback();
    },
    flush(callback) {
      // Push any remaining buffer
      if (buffer) {
        // Try one last time to inject if we have helmet data
        const helmetData = helmetContext.helmet;
        if (helmetData && !headInjected) {
          const headCloseIndex = buffer.indexOf('</head>');
          if (headCloseIndex !== -1) {
            const helmetHtml = [
              helmetData.title?.toString() || '',
              helmetData.meta?.toString() || '',
              helmetData.link?.toString() || '',
              helmetData.script?.toString() || '',
              helmetData.style?.toString() || '',
              helmetData.noscript?.toString() || '',
            ]
              .filter(Boolean)
              .join('\n    ');

            const beforeHead = buffer.substring(0, headCloseIndex);
            const afterHead = buffer.substring(headCloseIndex);
            buffer = beforeHead + '\n    ' + helmetHtml + '\n  ' + afterHead;
          }
        }
        this.push(Buffer.from(buffer, 'utf-8'));
      }
      callback();
    },
  });
}

export default function handleRequest(
  request: Request,
  responseStatusCode: number,
  responseHeaders: Headers,
  routerContext: EntryContext,
  loadContext: AppLoadContext,
) {
  // https://httpwg.org/specs/rfc9110.html#HEAD
  if (request.method.toUpperCase() === "HEAD") {
    return new Response(null, {
      status: responseStatusCode,
      headers: responseHeaders,
    });
  }

  return new Promise((resolve, reject) => {
    let shellRendered = false;
    const userAgent = request.headers.get("user-agent");

    // Ensure requests from bots and SPA Mode renders wait for all content to load before responding
    // https://react.dev/reference/react-dom/server/renderToPipeableStream#waiting-for-all-content-to-load-for-crawlers-and-static-generation
    const readyOption: keyof RenderToPipeableStreamOptions =
      (userAgent && isbot(userAgent)) || routerContext.isSpaMode
        ? "onAllReady"
        : "onShellReady";

    // Abort the rendering stream after the `streamTimeout` so it has time to
    // flush down the rejected boundaries
    let timeoutId: ReturnType<typeof setTimeout> | undefined = setTimeout(
      () => abort(),
      streamTimeout + 1000,
    );

    const helmetContext: any = {};

    const { pipe, abort } = renderToPipeableStream(
      <HelmetProvider context={helmetContext}>
        <ServerRouter context={routerContext} url={request.url} />
      </HelmetProvider>,
      {
        [readyOption]() {
          shellRendered = true;

          const body = new PassThrough({
            final(callback) {
              // Clear the timeout to prevent retaining the closure and memory leak
              clearTimeout(timeoutId);
              timeoutId = undefined;
              callback();
            },
          });

          // Create helmet injector transform
          // Note: For bots/crawlers (onAllReady), helmet data should be available
          // For regular users (onShellReady), it might not be, but we'll try to inject it anyway
          const helmetInjector = createHelmetInjector(helmetContext);
          
          // Pipe through helmet injector before creating the readable stream
          body.pipe(helmetInjector);

          const stream = createReadableStreamFromReadable(helmetInjector);

          responseHeaders.set("Content-Type", "text/html");
          const robotsTag = buildXRobotsTag();
          if (robotsTag) {
            responseHeaders.set("X-Robots-Tag", robotsTag);
          } else {
            responseHeaders.delete("X-Robots-Tag");
          }

          pipe(body);

          resolve(
            new Response(stream, {
              headers: responseHeaders,
              status: responseStatusCode,
            }),
          );
        },
        onShellError(error: unknown) {
          reject(error);
        },
        onError(error: unknown) {
          responseStatusCode = 500;
          // Log streaming rendering errors from inside the shell. Don't log errors
          // encountered during initial shell rendering since they'll reject and
          // get logged in handleDocumentRequest.
          if (shellRendered) {
            console.error(error);
          }
        },
      },
    );
  });
}
