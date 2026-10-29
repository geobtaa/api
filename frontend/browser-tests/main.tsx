import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ResourceViewer } from '../src/components/resource/ResourceViewer';
import { DownloadsTable } from '../src/components/resource/DownloadsTable';
import type { ImageNavigation, ImageSelection } from 'ogm-viewer/lib';
import '../src/index.css';

function Fixture() {
  const [scenario, setScenario] = useState('good');
  const [selection, setSelection] = useState<ImageSelection | null>(null);
  const [navigation, setNavigation] = useState<ImageNavigation | null>(null);
  const data = useMemo(() => {
    const references: Record<string, string> = {};
    if (!['arcgis', 'location'].includes(scenario)) {
      references['http://iiif.io/api/image'] =
        `${location.origin}/fixtures/iiif/single/info.json`;
      references['http://iiif.io/api/presentation#manifest'] =
        `${location.origin}/fixtures/manifest/${scenario === 'mixed' ? 'good' : scenario}`;
    }
    if (['arcgis', 'mixed'].includes(scenario))
      references['urn:x-esri:serviceType:ArcGIS#FeatureLayer'] =
        `${location.origin}/fixtures/FeatureServer/0`;
    return {
      id: scenario,
      attributes: {
        ogm: {
          id: scenario,
          dct_title_s: `Fixture ${scenario}`,
          gbl_resourceClass_sm: ['Maps'],
          gbl_mdVersion_s: 'Aardvark',
          dct_accessRights_s: 'Public',
          locn_geometry: 'ENVELOPE(-2,2,2,-2)',
          dct_references_s: references,
        },
      },
    };
  }, [scenario]);
  return (
    <main className="p-6">
      <h1 className="text-xl mb-4">Viewer and Downloads integration</h1>
      <label>
        Fixture{' '}
        <select
          aria-label="Fixture"
          value={scenario}
          onChange={(event) => setScenario(event.target.value)}
        >
          {[
            'good',
            'v2',
            'duplicate',
            'multi-image',
            'first-fails',
            'later-fails',
            'mixed',
            'arcgis',
            'location',
          ].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      <div className="grid grid-cols-[minmax(0,2fr)_minmax(300px,1fr)] gap-6 mt-4">
        <ResourceViewer
          data={data}
          onImageSelectionChange={setSelection}
          imageNavigation={navigation}
        />
        <DownloadsTable
          downloads={[
            {
              label: 'Publisher download',
              url: '/fixtures/publisher.zip',
              type: 'application/zip',
            },
          ]}
          resourceId={scenario}
          followViewer
          activeImage={selection}
          onImageNavigate={setNavigation}
        />
      </div>
      <output data-testid="selection" className="sr-only">
        {JSON.stringify(selection)}
      </output>
    </main>
  );
}
createRoot(document.getElementById('root')!).render(<Fixture />);
