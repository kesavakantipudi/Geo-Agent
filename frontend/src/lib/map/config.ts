/**
 * Map (tile) configuration. Tile service, attribution, and zoom limits are
 * configurable via environment variables so no provider key is hard-coded.
 * Defaults to OpenStreetMap raster tiles; respect their usage policy and
 * configure a different provider for production.
 */
export const MAP_TILE_URL =
  process.env.NEXT_PUBLIC_MAP_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

export const MAP_TILE_ATTRIBUTION =
  process.env.NEXT_PUBLIC_MAP_ATTRIBUTION ??
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

export const MAP_MAX_ZOOM = Number(process.env.NEXT_PUBLIC_MAP_TILE_MAX_ZOOM ?? 19);

export const MAP_DEFAULT_CENTER = { lat: 12.9716, lon: 77.5946 };
export const MAP_DEFAULT_ZOOM = 11;