import { describe, expect, it, vi } from 'vitest';
import { onUserMapMovement } from '../../mapping/userMovement';
function harness() {
  const events = new Map<string, (event: object) => void>();
  const callback = vi.fn();
  const off = vi.fn();
  const cleanup = onUserMapMovement(
    { on: (name, fn) => events.set(name, fn), off },
    callback
  );
  return {
    callback,
    cleanup,
    off,
    emit: (name: string, event = {}) => events.get(name)?.(event),
  };
}
describe('user camera movement', () => {
  it('ignores initialization, style changes, programmatic flights, and resize', () => {
    const h = harness();
    h.emit('moveend');
    h.emit('moveend');
    h.emit('movestart');
    h.emit('moveend');
    h.emit('movestart', { originalEvent: { type: 'resize' } });
    h.emit('moveend', { originalEvent: { type: 'resize' } });
    expect(h.callback).not.toHaveBeenCalled();
  });
  it.each(['mousedown', 'touchstart', 'wheel', 'keydown', 'click'])(
    'recognizes the first %s interaction and not subsequent passive movement',
    (type) => {
      const h = harness();
      h.emit('movestart', { originalEvent: { type } });
      h.emit('moveend');
      h.emit('moveend');
      expect(h.callback).toHaveBeenCalledTimes(1);
    }
  );
  it('removes listeners on cleanup', () => {
    const h = harness();
    h.cleanup();
    expect(h.off.mock.calls.map(([name]) => name)).toEqual([
      'movestart',
      'moveend',
    ]);
  });
});
