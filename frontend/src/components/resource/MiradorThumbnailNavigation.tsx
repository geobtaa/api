import { useEffect, useRef, type ReactNode } from 'react';
import { Paper } from '@mui/material';
import { ConnectedThumbnailCanvasGrouping } from 'mirador';
import {
  Grid,
  type CellComponentProps,
  type GridImperativeAPI,
} from 'react-window';
import { useTranslation } from 'react-i18next';

import {
  MIN_THUMBNAIL_WIDTH,
  SPACING,
  SCROLLBAR_SIZE,
  thumbnailColumnWidth,
  type Canvas,
} from '../../utils/miradorThumbnailLayout';

interface ThumbnailNavigationProps {
  children?: ReactNode;
  canvasGroupings: Canvas[][];
  canvasIndex: number;
  position: string;
  thumbnailNavigation: { height: number; width: number };
  viewingDirection?: string;
  windowId: string;
  hasNextCanvas?: boolean;
  hasPreviousCanvas?: boolean;
  setNextCanvas: () => void;
  setPreviousCanvas: () => void;
}

type CellProps = Pick<
  ThumbnailNavigationProps,
  'canvasGroupings' | 'position' | 'windowId'
>;

function ThumbnailCell(props: CellComponentProps<CellProps>) {
  return <ConnectedThumbnailCanvasGrouping {...props} />;
}

function HorizontalThumbnails({
  canvasGroupings,
  canvasIndex,
  thumbnailNavigation,
  viewingDirection,
  windowId,
  hasNextCanvas,
  hasPreviousCanvas,
  setNextCanvas,
  setPreviousCanvas,
}: ThumbnailNavigationProps) {
  const { t } = useTranslation();
  const gridRef = useRef<GridImperativeAPI | null>(null);
  const paperRef = useRef<HTMLDivElement>(null);
  const height = thumbnailNavigation.height - SPACING - SCROLLBAR_SIZE;
  const selectedColumn = canvasGroupings.findIndex((canvases) =>
    canvases.some((canvas) => canvas.index === canvasIndex)
  );

  useEffect(() => {
    if (selectedColumn < 0) return;
    gridRef.current?.scrollToColumn({ index: selectedColumn, align: 'auto' });
    paperRef.current?.focus({ preventScroll: true });
  }, [selectedColumn]);

  return (
    <Paper
      ref={paperRef}
      className="mirador-thumb-navigation"
      aria-label={t('thumbnailNavigation')}
      tabIndex={0}
      square
      elevation={0}
      onKeyDown={(event) => {
        if (event.key === 'ArrowRight' && hasNextCanvas) {
          event.preventDefault();
          setNextCanvas();
        } else if (event.key === 'ArrowLeft' && hasPreviousCanvas) {
          event.preventDefault();
          setPreviousCanvas();
        }
      }}
      sx={{
        width: '100%',
        '& .mirador-thumbnail-nav-canvas > div': {
          minWidth: MIN_THUMBNAIL_WIDTH,
          textAlign: 'center',
          backgroundColor: 'grey.100',
          '& img': { marginInline: 'auto' },
        },
      }}
    >
      <Grid
        gridRef={gridRef}
        columnCount={canvasGroupings.length}
        columnWidth={(index) =>
          thumbnailColumnWidth(canvasGroupings[index], height)
        }
        rowCount={1}
        rowHeight={height}
        dir={viewingDirection === 'right-to-left' ? 'rtl' : 'ltr'}
        style={{ height: thumbnailNavigation.height }}
        cellComponent={ThumbnailCell}
        cellProps={{ canvasGroupings, position: 'far-bottom', windowId }}
      />
    </Paper>
  );
}

/** Keep Mirador's connected cells, selection, and lazy image loading. Only
 * replace horizontal layout so virtual column widths agree with the hit areas.
 */
export function MiradorThumbnailNavigation(props: ThumbnailNavigationProps) {
  if (props.position !== 'far-bottom') return props.children;
  return <HorizontalThumbnails {...props} />;
}
