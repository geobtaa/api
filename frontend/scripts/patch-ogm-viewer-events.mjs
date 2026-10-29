// Temporary backport of vendor/ogm-viewer/active-image-events.patch for pinned 1.6.0.
// Keep the registry package and its worker bundles intact; fail on any unexpected artifact.
import { readFile, writeFile, copyFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const frontend = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..'
);
const packageRoot = path.join(frontend, 'node_modules/ogm-viewer');
const pkg = JSON.parse(
  await readFile(path.join(packageRoot, 'package.json'), 'utf8')
);
if (pkg.version !== '1.6.0')
  throw new Error(
    'Review/remove the OGM selection-event backport before upgrading ogm-viewer.'
  );
const directory = path.join(packageRoot, 'dist/components');
const marker = '// BTAA active-image events backport v2\n';
const legacyMarker = '// BTAA active-image events backport v1\n';
const dispatch = (event) =>
  `(detail)=>this.el.dispatchEvent(new CustomEvent("${event}",{detail,bubbles:true,composed:true}))`;
const patches = [
  {
    entry: 'ogm-image.js',
    sha: 'be16033c2022f9590133289d2266ed2b43794bbe4b35f99a72b8050a95f3ef88',
    edits: [
      [
        'this.viewer.addHandler("open",',
        `this.__imageSelectionCleanup=__observeImageSelection(this.el,this.viewer,()=>this.previewer,${dispatch('imageChange')}),this.viewer.addHandler("open",`,
      ],
      [
        'disconnectedCallback(){',
        'disconnectedCallback(){this.__imageSelectionCleanup?.();',
      ],
    ],
  },
  {
    entry: 'ogm-previews.js',
    sha: '6c2acdab6910a13719ee320550aaaca93b0c5d294e371ba1816c45b4cb9a5972',
    edits: [
      [
        'componentWillLoad(){return',
        `componentWillLoad(){this.__previewSelection=__observePreviewSelection(this.el,()=>this.tabs,${dispatch('previewChange')});return`,
      ],
      [
        'async onRecordChange(',
        'componentDidRender(){this.__previewSelection?.update()}disconnectedCallback(){this.__previewSelection?.disconnect()}async onRecordChange(',
      ],
      [
        'get tabs(){return this.previewers??this.recordPreviewers}',
        'get tabs(){return this.previewers??__preferManifest(this.recordPreviewers)}',
      ],
      ['e.label()', '__previewLabel(e)'],
    ],
  },
];
const outputs = [];
for (const patch of patches) {
  const entry = await readFile(path.join(directory, patch.entry), 'utf8');
  const chunk = entry.match(/from"\.\/([^"/]+\.js)"/)?.[1];
  if (!chunk) throw new Error(`Cannot locate OGM component ${patch.entry}`);
  const target = path.join(directory, chunk);
  let source = await readFile(target, 'utf8');
  if (source.startsWith(marker)) continue;
  if (source.startsWith(legacyMarker)) {
    // Restore the verified original before applying this revision of the patch.
    source = source.split('\n').slice(2).join('\n');
    for (const [before, after] of patch.edits.slice(0, 2).toReversed()) {
      if (source.split(after).length !== 2)
        throw new Error(`Unexpected legacy OGM patch: ${patch.entry}`);
      source = source.replace(after, before);
    }
  }
  if (createHash('sha256').update(source).digest('hex') !== patch.sha)
    throw new Error(`Unexpected OGM artifact: ${patch.entry}`);
  for (const [before, after] of patch.edits) {
    if (source.split(before).length !== 2)
      throw new Error(`Ambiguous OGM patch: ${patch.entry}`);
    source = source.replace(before, after);
  }
  outputs.push([
    target,
    marker +
      'import {observeImageSelection as __observeImageSelection,observePreviewSelection as __observePreviewSelection,preferManifest as __preferManifest,previewLabel as __previewLabel} from "./btaa-preview-events.js";\n' +
      source,
  ]);
}
await copyFile(
  path.join(frontend, 'vendor/ogm-viewer/preview-events.js'),
  path.join(directory, 'btaa-preview-events.js')
);
for (const [target, source] of outputs) await writeFile(target, source);
console.log('OGM Viewer 1.6.0 selection events ready.');
