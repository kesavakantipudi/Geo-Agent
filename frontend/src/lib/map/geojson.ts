/**
 * GeoJSON helpers shared by the map UI: extract a geometry from a Feature /
 * FeatureCollection / plain geometry, and export a geometry as a downloadable
 * GeoJSON Feature file.
 */

export function extractGeometry(value: unknown): unknown {
  if (!value || typeof value !== "object") return null;
  const candidate = value as {
    type?: string;
    geometry?: unknown;
    features?: unknown[];
  };
  if (candidate.type === "Feature") return candidate.geometry ?? null;
  if (candidate.type === "FeatureCollection") {
    const features = candidate.features ?? [];
    if (features.length !== 1) return null;
    const only = features[0] as { geometry?: unknown } | undefined;
    return only?.geometry ?? null;
  }
  return candidate;
}

export function downloadGeometryFeature(geometry: unknown, name: string) {
  const feature = {
    type: "Feature",
    properties: { name: name || "Area of interest", source: "geoagent" },
    geometry: geometry as GeoJSON.Geometry,
  };
  const blob = new Blob([JSON.stringify(feature, null, 2)], {
    type: "application/geo+json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "aoi.geojson";
  anchor.click();
  URL.revokeObjectURL(url);
}