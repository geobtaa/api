# Analytics

Analytics and observability configuration for deployed environments is
restricted operations material.

This public stub intentionally omits third-party dashboard identifiers,
container IDs, destination-specific enablement rules, verification procedures,
and deployment configuration. Google Analytics and Matomo are managed through
Google Tag Manager in the restricted operations documentation.

## Browser event contract

In production, the application loads Google Tag Manager only after browser
verification succeeds. This prevents the analytics container from recording
the verification screen or traffic that does not pass the gate. The Mirador
route remains excluded from the container.

The browser publishes the following custom events to `window.dataLayer`:

| Event               | When it fires                                    | Parameters                                                           |
| ------------------- | ------------------------------------------------ | -------------------------------------------------------------------- |
| `cite_copy`         | The formatted-citation copy button is clicked    | `resource_id`, `resource_title`                                      |
| `cite_export`       | A RIS, BibTeX, or JSON-LD export link is clicked | `resource_id`, `resource_title`, `format`                            |
| `cite_url`          | The Geoportal-link copy button is clicked        | `resource_id`, `resource_title`                                      |
| `virtual_page_view` | React Router completes a client-side navigation  | `page_location`, `page_path`, `page_title`, `previous_page_location` |

Citation events are click-only and are not emitted during page rendering. The
container's initial load remains responsible for the first page view;
`virtual_page_view` represents only later navigation within the single-page
application.

The deployed GTM workspace must map these stable event and parameter names to
the corresponding Google Analytics and Matomo tags. Container identifiers,
tag definitions, filters, preview evidence, and publishing procedures belong
in the restricted operations documentation.

For public, code-level context about first-party analytics events and storage,
see [Backend Analytics Program](backend/analytics_program.md). Do not add
production dashboard IDs, tag-manager IDs, or deployment secrets to public docs.
