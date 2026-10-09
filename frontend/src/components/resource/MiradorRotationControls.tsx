import type { ReactNode } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import { RotateCcw, RotateCw } from 'lucide-react';

interface RotationControlsProps {
  children: ReactNode;
  windowId: string;
  viewer?: { rotation?: number };
  updateViewport: (windowId: string, viewport: { rotation: number }) => void;
}

/** Extend Mirador's controls using its viewport state so pan and zoom are retained. */
export function MiradorRotationControls({
  children,
  windowId,
  viewer,
  updateViewport,
}: RotationControlsProps) {
  const rotate = (degrees: number) => {
    const rotation = ((viewer?.rotation ?? 0) + degrees + 360) % 360;
    updateViewport(windowId, { rotation });
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      {children}
      <Tooltip title="Rotate left 90°">
        <IconButton aria-label="Rotate left 90°" onClick={() => rotate(-90)}>
          <RotateCcw size={24} aria-hidden="true" />
        </IconButton>
      </Tooltip>
      <Tooltip title="Rotate right 90°">
        <IconButton aria-label="Rotate right 90°" onClick={() => rotate(90)}>
          <RotateCw size={24} aria-hidden="true" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
