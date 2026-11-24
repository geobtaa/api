/** Camera events also fire for layout/style changes. Only user input should
 * enable geographic search or pause the homepage's featured tour. */
export function onUserMapMovement(
  map: {
    on: (name: string, handler: (event: MovementEvent) => void) => unknown;
    off: (name: string, handler: (event: MovementEvent) => void) => unknown;
  },
  onMove: () => void
) {
  let userMove = false;
  const isInput = (event: MovementEvent) =>
    /^(mouse|pointer|touch|wheel|key|click|dblclick)/.test(
      event.originalEvent?.type ?? ''
    );
  const start = (event: MovementEvent) => {
    userMove = isInput(event);
  };
  const end = (event: MovementEvent) => {
    if (userMove || isInput(event)) onMove();
    userMove = false;
  };
  map.on('movestart', start);
  map.on('moveend', end);
  return () => {
    map.off('movestart', start);
    map.off('moveend', end);
  };
}
interface MovementEvent {
  originalEvent?: { type: string };
}
