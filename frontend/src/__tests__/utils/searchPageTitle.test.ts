import { describe, expect, it } from 'vitest';
import {
  buildSearchPageTitle,
  buildSearchPageTitleFromUrl,
} from '../../utils/searchPageTitle';

describe('searchPageTitle', () => {
  it('uses a keyword query when q has a value', () => {
    const params = new URLSearchParams('q=lakes');

    expect(buildSearchPageTitle(params)).toBe('Search: lakes');
  });

  it('keeps keyword queries alongside facet and bounding box constraints', () => {
    const params = new URLSearchParams();
    params.set('q', 'parks');
    params.append('include_filters[gbl_resourceClass_sm][]', 'Maps');
    params.set('include_filters[geo][type]', 'bbox');
    params.set('include_filters[geo][top_left][lat]', '42.785329');
    params.set('include_filters[geo][top_left][lon]', '-88.879677');
    params.set('include_filters[geo][bottom_right][lat]', '40.607704');
    params.set('include_filters[geo][bottom_right][lon]', '-86.608254');

    expect(buildSearchPageTitle(params)).toBe(
      'parks / Resource Class: Maps / Bounding Box: -88.879677 40.607704 -86.608254 42.785329'
    );
  });

  it('lists current facet constraints when q is missing', () => {
    const params = new URLSearchParams(
      'include_filters[dct_spatial_sm][]=Wisconsin&include_filters[gbl_resourceClass_sm][]=Maps&include_filters[gbl_resourceType_sm][]=Topographic+maps'
    );

    expect(buildSearchPageTitle(params)).toBe(
      'Place: Wisconsin / Resource Class: Maps / Resource Type: Topographic maps'
    );
  });

  it('lists legacy Geoportal facet constraints when q is empty', () => {
    const params = new URLSearchParams(
      'f%5Bdct_spatial_sm%5D%5B%5D=Wisconsin&f%5Bgbl_resourceClass_sm%5D%5B%5D=Maps&f%5Bgbl_resourceType_sm%5D%5B%5D=Topographic+maps&q=&search_field=all_fields'
    );

    expect(buildSearchPageTitle(params)).toBe(
      'Place: Wisconsin / Resource Class: Maps / Resource Type: Topographic maps'
    );
  });

  it('uses legacy bbox coordinates as a bounding box title', () => {
    const title = buildSearchPageTitleFromUrl(
      'https://geo.btaa.org/?bbox=-87.1418%2028.265814%20-50.799027%2060.34877'
    );

    expect(title).toBe('Bounding Box: -87.1418 28.265814 -50.799027 60.34877');
  });

  it('formats current geo filter params as west south east north', () => {
    const params = new URLSearchParams();
    params.set('include_filters[geo][type]', 'bbox');
    params.set('include_filters[geo][top_left][lat]', '60.34877');
    params.set('include_filters[geo][top_left][lon]', '-87.1418');
    params.set('include_filters[geo][bottom_right][lat]', '28.265814');
    params.set('include_filters[geo][bottom_right][lon]', '-50.799027');

    expect(buildSearchPageTitle(params)).toBe(
      'Bounding Box: -87.1418 28.265814 -50.799027 60.34877'
    );
  });

  it('includes year range, exclusions, and advanced clauses when present', () => {
    const params = new URLSearchParams();
    params.set('include_filters[year_range][start]', '1910');
    params.set('include_filters[year_range][end]', '1932');
    params.append('exclude_filters[dct_accessRights_s][]', 'Restricted');
    params.set(
      'adv_q',
      JSON.stringify([{ op: 'NOT', f: 'dct_title_s', q: 'draft' }])
    );

    expect(buildSearchPageTitle(params)).toBe(
      'Year Range: 1910 - 1932 / Exclude Access: Restricted / NOT Title: draft'
    );
  });
});
