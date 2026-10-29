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
    const clear = () => {
        const preview = getPreview();
        if (preview)
            emit({ ...selection(preview), image: null });
    };
    const opened = () => {
        const preview = getPreview();
        if (!preview)
            return;
        const index = viewer.currentPage();
        // OpenSeadragon exposes tileSources at runtime, but omits it from its Viewer type.
        const sources = viewer.tileSources ?? [];
        const source = sources?.[index];
        const url = typeof source === 'string' ? source : source?.tileSource;
        emit({
            ...selection(preview),
            image: typeof url === 'string'
                ? {
                    url,
                    index,
                    count: sources.length,
                    occurrence: sources.slice(0, index).filter(source => (typeof source === 'string' ? source : source?.tileSource) === url).length,
                }
                : null,
        });
    };
    viewer.addHandler('open', opened);
    for (const event of ['page', 'open-failed', 'close'])
        viewer.addHandler(event, clear);
    host.addEventListener('imageLoading', clear);
    return () => {
        viewer.removeHandler('open', opened);
        for (const event of ['page', 'open-failed', 'close'])
            viewer.removeHandler(event, clear);
        host.removeEventListener('imageLoading', clear);
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
