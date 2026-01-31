
import React, { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, Rectangle, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoDocument } from '../../types/api';
import type { LatLngBoundsExpression } from 'leaflet';
import L from 'leaflet';
import { Link } from 'react-router';

interface MapResultViewProps {
    results: GeoDocument[];
    highlightedResourceId?: string | null;
}

// Unified controller to handle both initial fit and highlighting interactions
const MapController: React.FC<{
    bounds: LatLngBoundsExpression[];
    highlightedId: string | null;
    features: { resource: GeoDocument; bounds: LatLngBoundsExpression }[];
}> = ({ bounds, highlightedId, features }) => {
    const map = useMap();

    useEffect(() => {
        // If there is a highlighted ID, zoom to it
        if (highlightedId) {
            const feature = features.find(f => f.resource.id === highlightedId);
            if (feature) {
                map.flyToBounds(feature.bounds as L.LatLngBoundsExpression, {
                    padding: [100, 100],
                    maxZoom: 8,
                    duration: 0.5
                });
            }
        }
        // If NO highlighted ID (hover leave), reset to all bounds
        else if (bounds && bounds.length > 0) {
            const group = L.featureGroup(bounds.map(b => L.rectangle(b as L.LatLngBoundsExpression)));
            if (group.getBounds().isValid()) {
                map.flyToBounds(group.getBounds(), {
                    padding: [50, 50],
                    duration: 0.5
                });
            }
        }
    }, [highlightedId, bounds, features, map]);

    return null;
};

export const MapResultView: React.FC<MapResultViewProps> = ({ results, highlightedResourceId }) => {
    // Parse BBoxes - Memoized to prevent re-calculation on every render (e.g. hover)
    const features = useMemo(() => results.map(r => {
        const bboxStr = r.attributes.ogm.dcat_bbox;
        if (!bboxStr) return null;

        let coords: [number, number, number, number] | null = null; // [minX, minY, maxX, maxY]

        // Try ENVELOPE(minX, maxX, maxY, minY) - Standard Aardvark
        const envelopeMatch = bboxStr.match(/ENVELOPE\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)/i);
        if (envelopeMatch) {
            const minX = parseFloat(envelopeMatch[1]);
            const maxX = parseFloat(envelopeMatch[2]);
            const maxY = parseFloat(envelopeMatch[3]);
            const minY = parseFloat(envelopeMatch[4]);
            coords = [minX, minY, maxX, maxY];
        } else {
            // Try CSV/Simple: minX,minY,maxX,maxY
            const parts = bboxStr.split(',').map(s => parseFloat(s.trim()));
            if (parts.length === 4 && parts.every(n => !isNaN(n))) {
                coords = [parts[0], parts[1], parts[2], parts[3]];
            }
        }

        if (!coords) return null;

        // Leaflet Bounds: [[minY, minX], [maxY, maxX]] (SouthWest, NorthEast)
        const bounds: LatLngBoundsExpression = [
            [coords[1], coords[0]],
            [coords[3], coords[2]]
        ];

        return { resource: r, bounds };
    }).filter(f => f !== null) as { resource: GeoDocument; bounds: LatLngBoundsExpression }[], [results]);

    const allBounds = useMemo(() => features.map(f => f.bounds), [features]);

    if (features.length === 0) {
        return (
            <div className="flex h-64 items-center justify-center text-slate-500 bg-gray-50 dark:bg-slate-900">
                No mappable results found in this page.
            </div>
        );
    }

    return (
        <div className="h-full w-full bg-slate-100 rounded-lg overflow-hidden relative z-0">
            <MapContainer
                center={[0, 0]}
                zoom={2}
                className="h-full w-full"
                scrollWheelZoom={true}
            >
                <TileLayer
                    url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                />

                {features.map(f => {
                    const isHighlighted = f.resource.id === highlightedResourceId;
                    return (
                        <Rectangle
                            key={f.resource.id}
                            bounds={f.bounds}
                            pathOptions={{
                                color: isHighlighted ? '#f59e0b' : '#6366f1', // Amber if highlighted, Indigo default
                                weight: isHighlighted ? 3 : 1,
                                fillOpacity: isHighlighted ? 0.3 : 0.1
                            }}
                        >
                            <Popup>
                                <div className="text-xs min-w-[200px]">
                                    <strong className="block mb-1 text-sm">{f.resource.attributes.ogm.dct_title_s}</strong>
                                    <span className="text-slate-500 block mb-2">{f.resource.id}</span>
                                    <Link
                                        to={`/resources/${f.resource.id}`}
                                        className="text-indigo-600 hover:text-indigo-800 font-medium hover:underline"
                                    >
                                        View Details
                                    </Link>
                                </div>
                            </Popup>
                        </Rectangle>
                    );
                })}

                <MapController bounds={allBounds} features={features} highlightedId={highlightedResourceId || null} />
            </MapContainer>
        </div>
    );
};
