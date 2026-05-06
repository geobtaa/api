declare module 'mirador' {
  type MiradorViewer = (
    config: Record<string, unknown>,
    plugins?: unknown[]
  ) => { destroy?: () => void; unmount?: () => void } | void;

  const Mirador: {
    viewer: MiradorViewer;
  };

  export const viewer: MiradorViewer;
  export default Mirador;
}

declare module 'mirador-dl-plugin' {
  const plugins: unknown[];
  export default plugins;
}
