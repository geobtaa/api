/** A manifest represents the complete object, so offer it before a standalone scan. */
export function preferManifest(previews) {
    const primary = previews.filter(preview => preview.kind === 'iiif-manifest' && preview.renderer === 'image');
    return [...primary, ...previews.filter(preview => !primary.includes(preview))];
}
export function previewLabel(preview) {
    if (preview.renderer === 'image' && preview.kind === 'iiif-manifest')
        return 'Images';
    if (preview.renderer === 'image' && preview.kind === 'iiif-image')
        return 'Single image';
    return preview.label();
}
function selection(preview) {
    return {
        previewId: preview.previewId,
        resourceId: preview.resourceId,
        resourceUrl: preview.url,
        renderer: preview.renderer,
    };
}
/** Report the source actually opened, and clear it while a page changes or fails. */
export function observeImageSelection(host, viewer, getPreview, emit) {
    const sourceUrl = (source) => {
        const url = typeof source === 'string' ? source : source?.tileSource;
        return typeof url === 'string' ? url : undefined;
    };
    const snapshot = () => {
        const occurrences = new Map();
        const sequence = [];
        (viewer.tileSources ?? []).forEach((source, index) => {
            const url = sourceUrl(source);
            if (!url)
                return;
            const occurrence = occurrences.get(url) ?? 0;
            occurrences.set(url, occurrence + 1);
            sequence.push({ url, index, occurrence });
        });
        return { sequence, pageIndex: viewer.currentPage() };
    };
    const clear = () => {
        const preview = getPreview();
        if (preview)
            emit({ ...selection(preview), ...snapshot(), image: null });
    };
    const opened = () => {
        const preview = getPreview();
        if (!preview)
            return;
        const state = snapshot();
        const image = state.sequence.find(image => image.index === state.pageIndex);
        emit({
            ...selection(preview),
            ...state,
            image: image ? { ...image, count: viewer.tileSources?.length ?? 0 } : null,
        });
    };
    // Requests are addressed to the public viewer host; each image validates its identity.
    // Standalone ogm-image elements receive the same request on their own host.
    let commandTarget = host;
    let ancestor = host;
    while (ancestor) {
        if (ancestor.nodeName === 'OGM-VIEWER') {
            commandTarget = ancestor;
            break;
        }
        ancestor = ancestor.parentNode ?? ancestor.host;
    }
    const navigate = (event) => {
        const request = event.detail;
        const preview = getPreview();
        if (!request ||
            !preview ||
            request.previewId !== preview.previewId ||
            request.resourceId !== preview.resourceId ||
            request.resourceUrl !== preview.url ||
            request.renderer !== 'image' ||
            !Number.isInteger(request.index) ||
            request.index < 0 ||
            request.index >= (viewer.tileSources?.length ?? 0) ||
            request.url !== sourceUrl(viewer.tileSources?.[request.index]))
            return;
        viewer.goToPage(request.index);
    };
    commandTarget.addEventListener('imageNavigationRequest', navigate);
    viewer.addHandler('open', opened);
    for (const event of ['page', 'open-failed', 'close'])
        viewer.addHandler(event, clear);
    host.addEventListener('imageLoading', clear);
    return () => {
        viewer.removeHandler('open', opened);
        for (const event of ['page', 'open-failed', 'close'])
            viewer.removeHandler(event, clear);
        host.removeEventListener('imageLoading', clear);
        commandTarget.removeEventListener('imageNavigationRequest', navigate);
    };
}
/** Publish the initial preview and tab switches, including transitions to non-image previews. */
export function observePreviewSelection(host, getPreviews, emit) {
    let signature;
    let activeId;
    let last;
    const opened = new Set();
    const failed = new Set();
    const isIiifImage = (preview) => preview.renderer === 'image' && (preview.kind === 'iiif-manifest' || preview.kind === 'iiif-image');
    const refreshAvailability = () => {
        host.shadowRoot?.querySelectorAll('wa-tab').forEach(tab => {
            const unavailable = failed.has(tab.getAttribute('panel') ?? '');
            // Keep the active error readable when every alternative has failed.
            tab.disabled = unavailable && tab.getAttribute('panel') !== activeId;
            if (unavailable)
                tab.setAttribute('title', 'Preview unavailable');
            else
                tab.removeAttribute('title');
        });
    };
    const recover = () => {
        if (!activeId || !failed.has(activeId) || opened.has(activeId))
            return;
        const fallback = getPreviews().find(preview => isIiifImage(preview) && opened.has(preview.previewId) && !failed.has(preview.previewId));
        if (!fallback)
            return;
        const group = host.shadowRoot?.querySelector('wa-tab-group');
        if (group)
            group.active = fallback.previewId;
    };
    const publish = (preview) => {
        const detail = preview ? selection(preview) : null;
        const serialized = JSON.stringify(detail);
        if (serialized !== last) {
            last = serialized;
            emit(detail);
        }
    };
    const update = () => {
        const previews = getPreviews();
        const next = JSON.stringify(previews.map(selection));
        if (next !== signature) {
            signature = next;
            activeId = previews[0]?.previewId;
            opened.clear();
            failed.clear();
        }
        publish(previews.find(preview => preview.previewId === activeId));
        refreshAvailability();
    };
    const shown = (event) => {
        const id = event.detail?.name;
        const preview = getPreviews().find(preview => preview.previewId === id);
        if (!preview)
            return;
        // An initial tab event can precede the first componentDidRender callback.
        signature = JSON.stringify(getPreviews().map(selection));
        activeId = id;
        publish(preview);
        refreshAvailability();
        recover();
    };
    const loaded = () => {
        // Reloading the same record can preserve preview IDs and the active tab.
        // Consumers cleared their selection on previewsLoading, so republish it.
        last = undefined;
        update();
    };
    const imageOpened = (event) => {
        const detail = event.detail;
        if (!detail?.image)
            return;
        const preview = getPreviews().find(preview => preview.previewId === detail.previewId && preview.resourceId === detail.resourceId && preview.url === detail.resourceUrl);
        if (!preview || !isIiifImage(preview))
            return;
        update();
        opened.add(preview.previewId);
        failed.delete(preview.previewId);
        refreshAvailability();
        recover();
    };
    const previewFailed = (event) => {
        // Capture before ogm-preview stops propagation. The public previewer property
        // identifies the failed image even when a manifest also has a map preview.
        const origin = event.composedPath().find(node => node.tagName === 'OGM-IMAGE');
        const source = origin?.previewer;
        const preview = source && getPreviews().find(preview => preview.previewId === source.previewId && preview.resourceId === source.resourceId && preview.url === source.url);
        if (!preview || !isIiifImage(preview))
            return;
        update();
        // Never abandon a book because a later sheet cannot load.
        if (opened.has(preview.previewId))
            return;
        failed.add(preview.previewId);
        refreshAvailability();
        recover();
    };
    const loading = () => {
        opened.clear();
        failed.clear();
        refreshAvailability();
    };
    host.addEventListener('previewsLoading', loading);
    host.addEventListener('imageChange', imageOpened);
    host.addEventListener('previewError', previewFailed, true);
    host.addEventListener('wa-tab-show', shown);
    host.addEventListener('previewsLoaded', loaded);
    return {
        update,
        disconnect: () => {
            host.removeEventListener('previewsLoading', loading);
            host.removeEventListener('imageChange', imageOpened);
            host.removeEventListener('previewError', previewFailed, true);
            host.removeEventListener('wa-tab-show', shown);
            host.removeEventListener('previewsLoaded', loaded);
        },
    };
}
