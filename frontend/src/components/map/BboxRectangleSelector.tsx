import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import L from 'leaflet';
import { useMap } from 'react-leaflet';

const BBOX_RECTANGLE_PANE = 'bboxRectangleSelectorPane';

function buildBboxSearchUrl(bounds: L.LatLngBounds, relation = 'intersects') {
  const ne = bounds.getNorthEast();
  const sw = bounds.getSouthWest();
  const params = new URLSearchParams();
  params.set('include_filters[geo][type]', 'bbox');
  params.set('include_filters[geo][field]', 'dcat_bbox');
  params.set('include_filters[geo][relation]', relation);
  params.set('include_filters[geo][top_left][lat]', ne.lat.toString());
  params.set('include_filters[geo][top_left][lon]', sw.lng.toString());
  params.set('include_filters[geo][bottom_right][lat]', sw.lat.toString());
  params.set('include_filters[geo][bottom_right][lon]', ne.lng.toString());
  return `/search?${params.toString()}`;
}

export function BboxRectangleSelector() {
  const map = useMap();
  const navigate = useNavigate();
  const draggingRef = useRef(false);
  const startRef = useRef<L.LatLng | null>(null);
  const rectRef = useRef<L.Rectangle | null>(null);
  const movedRef = useRef(false);
  const suppressNextClickRef = useRef(false);

  useEffect(() => {
    const ensurePane = () => {
      let pane = map.getPane(BBOX_RECTANGLE_PANE);
      if (!pane) {
        pane = map.createPane(BBOX_RECTANGLE_PANE);
        pane.style.setProperty('z-index', '415', 'important');
      }
    };

    const removeRect = () => {
      if (rectRef.current && map.hasLayer(rectRef.current)) {
        map.removeLayer(rectRef.current);
        rectRef.current = null;
      }
    };

    const latLngFromClientPoint = (clientX: number, clientY: number) => {
      const container = map.getContainer();
      const bounds = container.getBoundingClientRect();
      const point = L.point(clientX - bounds.left, clientY - bounds.top);
      return map.containerPointToLatLng(point);
    };

    const handleMouseDown = (event: MouseEvent) => {
      if (event.button !== 0 || (!event.ctrlKey && !event.metaKey)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      draggingRef.current = true;
      movedRef.current = false;
      startRef.current = latLngFromClientPoint(event.clientX, event.clientY);
      map.dragging.disable();
      ensurePane();
    };

    const handleMouseMove = (event: MouseEvent) => {
      if (!draggingRef.current || !startRef.current) return;
      event.preventDefault();

      const latlng = latLngFromClientPoint(event.clientX, event.clientY);
      movedRef.current = true;
      const bounds = L.latLngBounds(startRef.current, latlng);

      removeRect();
      rectRef.current = L.rectangle(bounds, {
        pane: BBOX_RECTANGLE_PANE,
        color: '#2563eb',
        weight: 2,
        fillColor: '#3b82f6',
        fillOpacity: 0.15,
      });
      rectRef.current.addTo(map);
    };

    const handleMouseUp = (event: MouseEvent) => {
      if (!draggingRef.current) return;
      event.preventDefault();
      event.stopPropagation();

      map.dragging.enable();
      draggingRef.current = false;
      suppressNextClickRef.current = movedRef.current;

      if (!rectRef.current) {
        startRef.current = null;
        removeRect();
        return;
      }

      const bounds = rectRef.current.getBounds();
      startRef.current = null;
      removeRect();

      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();
      if (Math.abs(ne.lat - sw.lat) < 1e-8 || Math.abs(ne.lng - sw.lng) < 1e-8) {
        return;
      }

      navigate(buildBboxSearchUrl(bounds));
    };

    const handleClickCapture = (event: MouseEvent) => {
      if (!suppressNextClickRef.current) return;
      event.preventDefault();
      event.stopPropagation();
      suppressNextClickRef.current = false;
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || !draggingRef.current) return;
      map.dragging.enable();
      draggingRef.current = false;
      startRef.current = null;
      removeRect();
    };

    const container = map.getContainer();
    container.addEventListener('mousedown', handleMouseDown, true);
    container.addEventListener('click', handleClickCapture, true);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      container.removeEventListener('mousedown', handleMouseDown, true);
      container.removeEventListener('click', handleClickCapture, true);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('keydown', handleKeyDown);
      removeRect();
      if (draggingRef.current) {
        map.dragging.enable();
      }
    };
  }, [map, navigate]);

  return null;
}
