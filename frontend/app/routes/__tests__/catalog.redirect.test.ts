import { describe, expect, it } from 'vitest';
import type { LoaderFunctionArgs } from 'react-router';
import { loader } from '../catalog.$id';

describe('catalog legacy redirect loader', () => {
  it('permanently redirects old catalog URLs to resource URLs', () => {
    const response = loader({
      params: { id: 'a10a0f50-994e-0134-2096-0050569601ca-c' },
      request: new Request(
        'https://geo.btaa.org/catalog/a10a0f50-994e-0134-2096-0050569601ca-c'
      ),
    } as LoaderFunctionArgs);

    expect(response.status).toBe(301);
    expect(response.headers.get('location')).toBe(
      '/resources/a10a0f50-994e-0134-2096-0050569601ca-c'
    );
  });

  it('preserves query params on redirected catalog URLs', () => {
    const response = loader({
      params: { id: 'p16022coll583:2574' },
      request: new Request(
        'https://geo.btaa.org/catalog/p16022coll583:2574?utm_source=legacy'
      ),
    } as LoaderFunctionArgs);

    expect(response.status).toBe(301);
    expect(response.headers.get('location')).toBe(
      '/resources/p16022coll583:2574?utm_source=legacy'
    );
  });

  it('sends old catalog child URLs to the resource detail page', () => {
    const response = loader({
      params: { id: 'a10a0f50-994e-0134-2096-0050569601ca-c', '*': 'raw' },
      request: new Request(
        'https://geo.btaa.org/catalog/a10a0f50-994e-0134-2096-0050569601ca-c/raw'
      ),
    } as LoaderFunctionArgs);

    expect(response.status).toBe(301);
    expect(response.headers.get('location')).toBe(
      '/resources/a10a0f50-994e-0134-2096-0050569601ca-c'
    );
  });

  it('returns a bad request when a catalog URL has no resource ID', () => {
    expect(() =>
      loader({
        params: {},
        request: new Request('https://geo.btaa.org/catalog/'),
      } as LoaderFunctionArgs)
    ).toThrow(Response);
  });
});
