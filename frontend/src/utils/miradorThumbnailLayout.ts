export const MIN_THUMBNAIL_WIDTH = 80;
// Match Mirador's cell padding and reserved scrollbar space.
export const SPACING = 12;
export const SCROLLBAR_SIZE = 6;

export interface Canvas {
  index: number;
  getWidth: () => number;
  getHeight: () => number;
}

export function thumbnailColumnWidth(canvases: Canvas[], height: number) {
  return (
    Math.ceil(
      canvases.reduce((width, canvas) => {
        const scaledWidth = (height * canvas.getWidth()) / canvas.getHeight();
        return (
          width +
          (Number.isFinite(scaledWidth)
            ? Math.max(MIN_THUMBNAIL_WIDTH, scaledWidth)
            : MIN_THUMBNAIL_WIDTH)
        );
      }, 0)
    ) + SPACING
  );
}
