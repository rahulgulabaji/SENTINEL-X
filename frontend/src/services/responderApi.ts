/**
 * Responder registry service boundary.
 *
 * The real SENTINEL-X backend has no responder/dispatch registry — zero
 * matches for responder/dispatch/sms/notify anywhere server-side. Officer
 * names, phone numbers, coordinates, and availability shown by any
 * prototype are fabricated and must never be presented as real.
 *
 * This module returns an empty list until the forthcoming Map API
 * supplies real responder data. The shape below is what the UI consumes;
 * swapping the body of `getResponders()` later requires no call-site
 * changes.
 */

export interface ResponderRecord {
  id: string;
  name: string;
  unit: string;
  role: string;
  phone: string;
  lat: number;
  lng: number;
  status: "AVAILABLE" | "BUSY";
  lastUpdated: string;
}

/**
 * Returns the list of real, Map-API-known responders. Currently always
 * empty — no real responder source is wired up yet.
 */
export async function getResponders(): Promise<ResponderRecord[]> {
  return [];
}
