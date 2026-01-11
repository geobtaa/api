// ESM shim for the `void-elements` package (which is CommonJS).
// Some ESM consumers expect a default export; Vite can otherwise surface:
// "does not provide an export named 'default'".
const voidElements = {
  area: true,
  base: true,
  br: true,
  col: true,
  embed: true,
  hr: true,
  img: true,
  input: true,
  link: true,
  meta: true,
  param: true,
  source: true,
  track: true,
  wbr: true,
} as const;

export default voidElements;
