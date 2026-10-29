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
        }
        publish(previews.find(preview => preview.previewId === activeId));
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
    };
    const loaded = () => {
        // Reloading the same record can preserve preview IDs and the active tab.
        // Consumers cleared their selection on previewsLoading, so republish it.
        last = undefined;
        update();
    };
    host.addEventListener('wa-tab-show', shown);
    host.addEventListener('previewsLoaded', loaded);
    return {
        update,
        disconnect: () => {
            host.removeEventListener('wa-tab-show', shown);
            host.removeEventListener('previewsLoaded', loaded);
        },
    };
}
