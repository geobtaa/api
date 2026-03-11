import { describe, expect, it } from 'vitest';
import { getStaticMapSearchEnvelope } from '../../utils/bbox';

describe('getStaticMapSearchEnvelope', () => {
  it('returns a valid northwest/southeast envelope around the center point', () => {
    const envelope = getStaticMapSearchEnvelope(39.1702, -86.5235, 15);

    expect(envelope.topLeft.lat).toBeGreaterThan(39.1702);
    expect(envelope.topLeft.lon).toBeLessThan(-86.5235);
    expect(envelope.bottomRight.lat).toBeLessThan(39.1702);
    expect(envelope.bottomRight.lon).toBeGreaterThan(-86.5235);
  });

  it('gets tighter as zoom increases', () => {
    const zoom14 = getStaticMapSearchEnvelope(39.1702, -86.5235, 14);
    const zoom16 = getStaticMapSearchEnvelope(39.1702, -86.5235, 16);
    const zoom14Width = zoom14.bottomRight.lon - zoom14.topLeft.lon;
    const zoom16Width = zoom16.bottomRight.lon - zoom16.topLeft.lon;

    expect(zoom16Width).toBeLessThan(zoom14Width);
  });
});
