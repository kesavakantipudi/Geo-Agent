"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import type { GeoJSON as LeafletGeoJSON } from "leaflet";

import type { Centroid, GeoJsonGeometry } from "@/lib/api/types";
import {
  MAP_DEFAULT_CENTER,
  MAP_DEFAULT_ZOOM,
  MAP_MAX_ZOOM,
  MAP_TILE_ATTRIBUTION,
  MAP_TILE_URL,
} from "@/lib/map/config";

import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

export type DrawMode = "polygon" | "rectangle";

export interface ChangeMaskOverlay {
  bounds: { west: number; south: number; east: number; north: number };
  data_uri: string;
}

interface LocationMapProps {
  aoi: GeoJsonGeometry | null;
  drawMode: DrawMode | null;
  onDrawCreated: (geometry: GeoJsonGeometry) => void;
  placeCenter: Centroid | null;
  maskOverlay?: ChangeMaskOverlay | null;
}

function DrawControl({
  drawMode,
  onDrawCreated,
}: {
  drawMode: DrawMode | null;
  onDrawCreated: (geometry: GeoJsonGeometry) => void;
}) {
  const map = useMap() as L.DrawMap;
  const handlerRef = useRef<{ enable: () => void; disable: () => void } | null>(null);

  useEffect(() => {
    if (!drawMode) return;

    const handler =
      drawMode === "polygon"
        ? new L.Draw.Polygon(map, { allowIntersection: false, showArea: true })
        : new L.Draw.Rectangle(map, {});
    handlerRef.current = handler;
    handler.enable();

    const handleCreated = (event: L.DrawEvents.Created) => {
      const layer = event.layer;
      if (!layer) return;
      const feature = layer.toGeoJSON();
      if (feature.geometry) {
        onDrawCreated(feature.geometry as GeoJsonGeometry);
      }
      handler.disable();
    };

    const onCreated = handleCreated as L.LeafletEventHandlerFn;
    map.on(L.Draw.Event.CREATED, onCreated);

    return () => {
      map.off(L.Draw.Event.CREATED, onCreated);
      handler.disable();
      handlerRef.current = null;
    };
  }, [drawMode, map, onDrawCreated]);

  return null;
}

function AoiOverlay({ aoi }: { aoi: GeoJsonGeometry | null }) {
  const map = useMap();
  const layerRef = useRef<LeafletGeoJSON | null>(null);

  useEffect(() => {
    layerRef.current?.remove();
    layerRef.current = null;
    if (!aoi) return;

    const layer = L.geoJSON(aoi as unknown as GeoJSON.GeoJSON, {
      style: { color: "#2563eb", weight: 2, fillColor: "#2563eb", fillOpacity: 0.18 },
    });
    layer.addTo(map);
    const bounds = layer.getBounds();
    if (bounds.isValid() && !bounds.equals(map.getBounds())) {
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 16 });
    }
    layerRef.current = layer;

    return () => {
      layerRef.current?.remove();
      layerRef.current = null;
    };
  }, [aoi, map]);

  return null;
}

function PlaceMarker({ placeCenter }: { placeCenter: Centroid | null }) {
  const map = useMap();

  useEffect(() => {
    if (!placeCenter) return;
    const icon = L.divIcon({
      className: "geo-pin",
      html: '<div class="geo-pin__dot"></div>',
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    });
    const marker = L.marker([placeCenter.lat, placeCenter.lon], {
      icon,
      zIndexOffset: 1000,
    }).addTo(map);
    map.setView([placeCenter.lat, placeCenter.lon], Math.max(map.getZoom() ?? 0, 13));

    return () => {
      marker.remove();
    };
  }, [placeCenter, map]);

  return null;
}

function MaskOverlay({ overlay }: { overlay: ChangeMaskOverlay | null | undefined }) {
  const map = useMap();
  const layerRef = useRef<L.ImageOverlay | null>(null);

  useEffect(() => {
    layerRef.current?.remove();
    layerRef.current = null;
    if (!overlay) return;

    const bounds = L.latLngBounds(
      [overlay.bounds.south, overlay.bounds.west],
      [overlay.bounds.north, overlay.bounds.east],
    );
    const layer = L.imageOverlay(overlay.data_uri, bounds, {
      opacity: 0.75,
      interactive: false,
    }).addTo(map);
    if (bounds.isValid() && !bounds.equals(map.getBounds())) {
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 16 });
    }
    layerRef.current = layer;

    return () => {
      layerRef.current?.remove();
      layerRef.current = null;
    };
  }, [overlay, map]);

  return null;
}

export function LocationMap({
  aoi,
  drawMode,
  onDrawCreated,
  placeCenter,
  maskOverlay,
}: LocationMapProps) {
  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={[MAP_DEFAULT_CENTER.lat, MAP_DEFAULT_CENTER.lon]}
        zoom={MAP_DEFAULT_ZOOM}
        maxZoom={MAP_MAX_ZOOM}
        scrollWheelZoom
        className="h-full w-full"
        style={{ background: "#e7e5e4" }}
      >
        <TileLayer attribution={MAP_TILE_ATTRIBUTION} url={MAP_TILE_URL} maxZoom={MAP_MAX_ZOOM} />
        <DrawControl drawMode={drawMode} onDrawCreated={onDrawCreated} />
        <AoiOverlay aoi={aoi} />
        <MaskOverlay overlay={maskOverlay} />
        <PlaceMarker placeCenter={placeCenter} />
      </MapContainer>
      {drawMode && (
        <div className="pointer-events-none absolute inset-x-0 top-3 z-[1000] flex justify-center">
          <span className="rounded-full bg-zinc-900/85 px-3 py-1 text-xs font-medium text-white">
            Draw a {drawMode} on the map to define the area of interest
          </span>
        </div>
      )}
    </div>
  );
}