---
version: alpha
name: BTAA Geoportal
description: Design guidance for the React/Tailwind frontend of the BTAA Geospatial API and Geoportal.
colors:
  primary: "#003C5B"
  primary-hover: "#002F49"
  primary-dark: "#002A41"
  active: "#2563EB"
  active-hover: "#1D4ED8"
  active-soft: "#EFF6FF"
  active-light: "#DBEAFE"
  on-primary: "#FFFFFF"
  surface: "#FFFFFF"
  surface-muted: "#F9FAFB"
  surface-subtle: "#F8FAFC"
  text-primary: "#111827"
  text-secondary: "#4B5563"
  text-muted: "#6B7280"
  border: "#E5E7EB"
  border-strong: "#D1D5DB"
  tag-subject-bg: "#DBEAFE"
  tag-subject-text: "#1E40AF"
  tag-theme-bg: "#F3E8FF"
  tag-theme-text: "#6B21A8"
  danger: "#DC2626"
  danger-soft: "#FEF2F2"
  warning: "#F59E0B"
  map-blue-100: "#DBEAFE"
  map-blue-200: "#BFDBFE"
  map-blue-300: "#93C5FD"
  map-blue-400: "#7AB3FD"
  map-blue-500: "#60A5FA"
  map-blue-600: "#3B82F6"
  map-blue-700: "#2563EB"
  map-blue-800: "#1D4ED8"
  map-blue-900: "#1E40AF"
typography:
  headline-lg:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 30px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0em
  headline-md:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: 0em
  headline-sm:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: 0em
  body-md:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: 0em
  label-md:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.25
    letterSpacing: 0em
  label-caps:
    fontFamily: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: 0.14em
  metadata-mono:
    fontFamily: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, Courier New, monospace
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0em
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  2xl: 40px
  page-x-mobile: 16px
  page-x-sm: 24px
  page-x-lg: 32px
  section-y: 40px
  card-padding: 24px
rounded:
  none: 0px
  xs: 2px
  sm: 4px
  md: 6px
  lg: 8px
  full: 9999px
components:
  header:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.none}"
  footer-btaa:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.none}"
  footer-utility-panel:
    backgroundColor: "{colors.primary-dark}"
    textColor: "{colors.on-primary}"
    typography: "{typography.metadata-mono}"
    rounded: "{rounded.lg}"
    padding: 12px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 8px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.full}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.full}"
    padding: 8px
  search-input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 12px
  link-primary:
    textColor: "{colors.active}"
    typography: "{typography.label-md}"
  link-primary-hover:
    textColor: "{colors.active-hover}"
    typography: "{typography.label-md}"
  result-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.lg}"
    padding: 24px
  page-background:
    backgroundColor: "{colors.surface-muted}"
  featured-row:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.body-md}"
    padding: 24px
  facet-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.none}"
    padding: 8px
  facet-row-active:
    backgroundColor: "{colors.active-soft}"
    textColor: "{colors.active}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 4px
  active-light-surface:
    backgroundColor: "{colors.active-light}"
    rounded: "{rounded.md}"
  facet-divider:
    backgroundColor: "{colors.border}"
    rounded: "{rounded.none}"
  input-border:
    backgroundColor: "{colors.border-strong}"
    rounded: "{rounded.sm}"
  metadata-muted:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-muted}"
    typography: "{typography.body-sm}"
  chip-subject:
    backgroundColor: "{colors.tag-subject-bg}"
    textColor: "{colors.tag-subject-text}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    padding: 4px
  chip-theme:
    backgroundColor: "{colors.tag-theme-bg}"
    textColor: "{colors.tag-theme-text}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
    padding: 4px
  resource-pill:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-caps}"
    rounded: "{rounded.sm}"
    padding: 4px
  danger-exclude:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.danger}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: 4px
  danger-soft-surface:
    backgroundColor: "{colors.danger-soft}"
    rounded: "{rounded.md}"
  warning-highlight:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.text-primary}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.full}"
  map-hex-high:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.none}"
  map-hex-100:
    backgroundColor: "{colors.map-blue-100}"
    rounded: "{rounded.none}"
  map-hex-200:
    backgroundColor: "{colors.map-blue-200}"
    rounded: "{rounded.none}"
  map-hex-300:
    backgroundColor: "{colors.map-blue-300}"
    rounded: "{rounded.none}"
  map-hex-400:
    backgroundColor: "{colors.map-blue-400}"
    rounded: "{rounded.none}"
  map-hex-500:
    backgroundColor: "{colors.map-blue-500}"
    rounded: "{rounded.none}"
  map-hex-600:
    backgroundColor: "{colors.map-blue-600}"
    rounded: "{rounded.none}"
  map-hex-700:
    backgroundColor: "{colors.map-blue-700}"
    rounded: "{rounded.none}"
  map-hex-800:
    backgroundColor: "{colors.map-blue-800}"
    rounded: "{rounded.none}"
  map-hex-900:
    backgroundColor: "{colors.map-blue-900}"
    rounded: "{rounded.none}"
  map-hex-selected:
    backgroundColor: "{colors.map-blue-600}"
    rounded: "{rounded.none}"
---

# DESIGN.md

## Overview

BTAA Geoportal is a research and discovery interface for geospatial resources. It should feel institutional, clear, map-forward, and fast to scan. The visual system is practical: a deep BTAA blue anchors navigation and calls to action; white and cool gray surfaces carry dense metadata; maps, thumbnails, and partner logos provide most of the visual richness.

The frontend is built with React and Tailwind. The active brand color is exposed as `brand` and `brand-active` in Tailwind, backed by CSS variables in `frontend/src/config/theme.css` and values from the BTAA entry in `frontend/theme.yaml`. New UI should preserve this structure and avoid hard-coding a new brand system unless a component genuinely needs a one-off data visualization color.

Design for repeated research workflows rather than marketing. Users need to search, filter, compare, preview, map, and inspect records. Interfaces should be information-dense but orderly, with predictable controls, stable dimensions, and accessible focus states.

## Colors

The primary palette is anchored in BTAA blue:

- **Primary (#003C5B):** Main header, BTAA footer, resource-class pills, partner tiles, logo mark, PWA theme color, and important spatial UI.
- **Primary hover (#002F49):** Hover treatment for primary pill buttons.
- **Primary dark (#002A41):** Footer utility panels and nested controls on dark blue.
- **Active (#2563EB):** Focus rings, active controls, selected map overlays, links where the app is in a task flow.
- **Surface (#FFFFFF), muted surfaces (#F9FAFB, #F8FAFC):** Page sections, cards, result rows, empty/loading states.
- **Text (#111827, #4B5563, #6B7280):** High-contrast headings, secondary body copy, and metadata.
- **Borders (#E5E7EB, #D1D5DB):** Structure comes mostly from borders and tonal contrast, not heavy decoration.

Maps use data colors, but they should still harmonize with the product. H3 hex density uses a light-to-dark blue ramp ending at BTAA blue. Boundary/selection overlays commonly use `#2563EB` strokes with `#3B82F6` fill at low opacity. Use warm ramps only where the existing regional/county choropleth code already does.

## Typography

Use the sans-serif stack declared in `frontend/theme.yaml`: Inter first, then system UI fallbacks. The app currently relies on Tailwind's typographic rhythm and simple font weights. Keep it that way.

- **Headlines:** 24-30px, semibold, gray-900. Use for page sections, resource titles, featured collection titles, and modal headings.
- **Result titles and links:** Semibold blue links for actionable resource names, usually `text-blue-600` with `hover:text-blue-800`.
- **Body:** 14-16px, gray-600 or gray-700, with short paragraphs and line clamping where records can be verbose.
- **Labels:** 12px uppercase semibold with positive tracking for small metadata labels, category ribbons, and facet headings.
- **Monospace:** Only for API URLs, debugging output, and code-like identifiers.

The BTAA header lockup uses `/btaa-logo.png` plus a "Geoportal" text lockup styled from `frontend/theme.yaml`. That lockup currently names Work Sans as the preferred font for the right-side text, with system fallbacks.

## Layout

The app uses full-width operational layouts, not centered marketing pages. Page gutters are Tailwind's standard `px-4 sm:px-6 lg:px-8`. Main pages use `bg-gray-50`; content sections and cards generally sit on white.

Key patterns:

- Header: sticky, full width, brand background, logo at left, search centered, navigation at right on desktop, slide-out menu below desktop.
- Search page: 12-column grid on large screens, with filters in a 3-column sidebar and results in a 9-column main region.
- Resource page: 12-column grid, main viewer/details at 8 columns and metadata at 4 columns.
- Homepage: map-first hero with a functional Leaflet/H3 surface, followed by full-width white content bands.
- Repeated items: result cards, gallery cards, featured collection rows, partner tiles, and blog cards.

Prefer stable dimensions for thumbnails, map controls, carousels, tiles, and icon buttons. Search result list thumbnails are 192px square by default and 96px square in compact contexts. Featured carousel controls are 64px square. Partner institution tiles use a minimum height around 84px.

Spacing follows Tailwind's 4px-based scale. Common page and section padding is 16/24/32px horizontally and around 40px vertically.

## Elevation & Depth

Depth is restrained and functional. Use shadow to separate sticky navigation, cards, overlays, and map popovers. Avoid decorative depth.

- Header: `shadow-[0_2px_10px_rgba(0,0,0,0.15)]`.
- Result cards: `shadow-md` with `hover:shadow-lg`.
- Map popovers and carousel: light borders, white or translucent white backgrounds, `shadow-lg`, and subtle backdrop blur.
- Footer and content bands: use borders and background contrast rather than shadow.

Use translucent white overlays on maps when needed, but keep content readable. Current homepage overlays use white at roughly 60-72 percent opacity with blur.

## Shapes

The shape language is modest and utility-focused.

- Standard cards and panels use `rounded-lg` (8px).
- Inputs and segmented controls commonly use `rounded-md` or `rounded-lg`.
- Pills, tags, and primary/secondary CTA buttons use `rounded-full`.
- Resource-card metadata pills use a small 4px radius.
- Homepage featured collection previews intentionally use clipped/slanted image masks; reserve that treatment for editorial/featured collection media, not ordinary app panels.
- Do not introduce large ornamental rounded panels or nested cards inside cards.

## Components

**Logos and brand assets**

- Default header logo: `/btaa-logo.png` (651 x 383) with a "Geoportal" lockup.
- App/fav/PWA mark: `/logo.svg`, `/favicon.ico`, `/pwa-64x64.png`, `/pwa-192x192.png`, `/pwa-512x512.png`.
- Footer BTAA-GIN logo: `/gin-white.png` (580 x 160) on BTAA blue.
- Partner/provider logos live in `/icons/*.svg`. On partner tiles they are often inverted to white over BTAA blue/map imagery unless a specific asset is marked non-monochrome.

**Icons**

Use `lucide-react` for interface icons. Existing icons include menu/close, search, map pin, arrows, chevrons, list/grid/map view toggles, bookmark, table, hexagon, external link, alert, and plus/remove actions. Keep lucide icons at 16-24px for controls and 32px only where the existing carousel/home controls use large hit targets.

Resource-class fallback icons are custom inline SVGs from `frontend/src/utils/resourceIcons.tsx`. They use BTAA blue and support Datasets, Maps, Web Services, Collections, Imagery, Websites, and Other. Reuse this utility rather than inventing new resource-class marks.

**Buttons and links**

Primary CTAs use `primaryCtaClass`: brand background, white text, full radius, 14px medium text, 8px vertical and 16px horizontal padding, brand-active focus ring, `#002F49` hover. Secondary CTAs use white background, gray border, gray-800 text, and the same shape/spacing.

Icon-only buttons need clear `aria-label` and visible focus rings. Prefer familiar icons over text labels for compact controls such as close, previous/next, view toggles, map tools, bookmarks, and search settings.

**Search and facets**

Search is the central workflow. Keep search controls dense, clear, and keyboard accessible. Advanced search uses blue-tinted borders and focus rings. Facets use `details/summary` accordions, gray text, blue active states, and red exclusion controls. Facet rows should not look like decorative cards.

**Results**

List results are white cards with rounded corners, shadow, thumbnail/media at left, title and metadata at right, and a static map preview at far right. Titles are blue links. Subject tags use blue chips; theme tags use purple chips. The compact variant preserves the same hierarchy with smaller thumbnail and typography.

**Maps**

Leaflet/OpenLayers controls should feel like map tools: square or compact controls, white backgrounds, gray borders, blue focus rings, and clear iconography. H3 hexes use the blue ramp in the tokens. Selected/geospatial overlays use blue strokes and transparent blue fills. Keep map controls out of decorative cards.

**Homepage**

The homepage starts with a working map hero, not a marketing card. It may use a translucent description overlay, a functional featured-resource carousel, and real map/resource imagery. Subsequent sections are full-width bands for featured collections, browse facets, partner institutions, and GIN stories.

**Documentation site**

The public MkDocs site has its own Material theme configuration and extra CSS under `mkdocs/`. Do not assume frontend component styles automatically apply there. Keep shared brand color choices aligned where practical, especially BTAA blue and white logo treatments.

## Do's and Don'ts

- Do use `brand` and `brand-active` Tailwind colors for application chrome and primary actions.
- Do keep BTAA blue as the default brand anchor and source shared color values from `frontend/theme.yaml` or `frontend/src/config/theme.css`.
- Do use lucide icons for interface actions and existing `/icons/*.svg` assets for institutions/providers.
- Do keep research workflows dense, scannable, and stable across responsive breakpoints.
- Do use white/gray surfaces with borders and modest shadows for hierarchy.
- Do keep map UI functional, visible, and accessible; maps and thumbnails should show real geospatial content when available.
- Do preserve high-contrast text and focus states.
- Don't create a marketing landing page when the user asked for app functionality.
- Don't introduce a new one-off palette for ordinary UI; reserve special ramps for data visualization.
- Don't overuse gradients, oversized hero type, decorative panels, or nested cards.
- Don't use heavy shadows where a border or tonal shift is enough.
- Don't replace existing theme assets or institution logos with generated art.
- Don't hard-code BTAA colors in new theme-aware components when `brand`/`brand-active` would work.
