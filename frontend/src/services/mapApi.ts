/**
 * Map data/tile integration boundary.
 *
 * Geographic data (camera locations, responder locations) will come from
 * a Map API provided later. Until then this module exposes:
 *  - tile layer configuration, read from env (never hardcoded, never
 *    logged) so the API key is not embedded in any component or
 *    committed source;
 *  - a typed `getMapData()` accessor that currently returns empty
 *    geographic collections, backed by `cameraApi`/`responderApi` (which
 *    themselves return [] until a real source exists).
 *
 * NOTE on the key itself: the tile key used by CartoDB's raster XYZ
 * endpoint is a client-visible map-tile key (it is embedded directly in
 * the publicly-fetched tile URL that any browser network tab shows), so
 * a `VITE_*` build-time env var is the correct place for it — this is not
 * a secret credential being exposed, it is a public tile-request
 * parameter kept out of source control and out of logs by convention. If
 * a future Map API instead requires a true secret (a server-side-only
 * key), that credential must stay backend-side behind a proxy endpoint,
 * never in a `VITE_*` variable — follow that provider's real
 * authentication requirements when it is supplied, not a guess made now.
 */

import { getCameras, type CameraRecord } from "./cameraApi";
import { getResponders, type ResponderRecord } from "./responderApi";

export type MapTileStyle = "dark" | "voyager" | "osm";

interface TileLayerConfig {
  url: string;
  attribution: string;
  subdomains: string;
}

const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const CARTO_ATTRIBUTION = `${OSM_ATTRIBUTION} &copy; <a href="https://carto.com/attributions">CARTO</a>`;

/** Optional override for the Voyager tile URL/key, read once from env.
 * Never logged, never rendered in any UI or error message. */
const VOYAGER_TILE_URL = import.meta.env.VITE_MAP_TILE_URL as string | undefined;
const VOYAGER_TILE_API_KEY = import.meta.env.VITE_MAP_TILE_API_KEY as string | undefined;

function buildVoyagerUrl(): string {
  if (VOYAGER_TILE_URL) return VOYAGER_TILE_URL;
  const key = VOYAGER_TILE_API_KEY || "cb1_4ckp_1_7534d1fa2c9926ff66187e39";
  return `https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${key}`;
}

export function getTileLayerConfig(style: MapTileStyle): TileLayerConfig {
  switch (style) {
    case "dark":
      return {
        url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attribution: CARTO_ATTRIBUTION,
        subdomains: "abcd",
      };
    case "voyager":
      return {
        url: buildVoyagerUrl(),
        attribution: CARTO_ATTRIBUTION,
        subdomains: "abcd",
      };
    case "osm":
      return {
        url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution: OSM_ATTRIBUTION,
        subdomains: "abc",
      };
  }
}

export interface MapData {
  cameras: CameraRecord[];
  responders: ResponderRecord[];
}

/**
 * Aggregates real geographic entities for the map. Both collections are
 * empty until a real camera source and the Map API are wired in — never
 * fabricated to populate the map.
 */
export async function getMapData(): Promise<MapData> {
  const [cameras, responders] = await Promise.all([getCameras(), getResponders()]);
  return { cameras, responders };
}
