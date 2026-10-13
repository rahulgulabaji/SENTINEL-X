import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { getTileLayerConfig } from "../../services/mapApi";
import type { ResponderRecord } from "../../services/responderApi";
import type { ActiveSource } from "./types";
import { Icons } from "./icons";

/**
 * Geographic map modal. Preserves the approved Leaflet-based map exactly
 * — same tile styling, same modal structure — but renders no fabricated
 * camera/responder markers. The real camera has geographic coordinates
 * only once a real registry/Map API supplies them (uploaded videos never
 * do); real responder markers only once the Map API supplies them.
 */
export function MapModal({
  source,
  responders,
  selectedResponderId,
  onSelectResponder,
  onClose,
  onRequestDispatch,
}: {
  source: ActiveSource;
  responders: ResponderRecord[];
  selectedResponderId: string | null;
  onSelectResponder: (id: string | null) => void;
  onClose: () => void;
  onRequestDispatch: () => void;
}) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Marker[]>([]);

  const cameraCoords = source.kind === "registry" && source.lat != null && source.lng != null ? { lat: source.lat, lng: source.lng } : null;

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const defaultCenter: [number, number] = cameraCoords ? [cameraCoords.lat, cameraCoords.lng] : [20, 0];
    const defaultZoom = cameraCoords ? 13 : 2;

    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: defaultZoom,
      zoomControl: true,
      attributionControl: true,
    });

    const tile = getTileLayerConfig("dark");
    L.tileLayer(tile.url, { attribution: tile.attribution, subdomains: tile.subdomains, maxZoom: 19 }).addTo(map);

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    for (const marker of markersRef.current) marker.remove();
    markersRef.current = [];

    if (cameraCoords) {
      const cameraIcon = L.divIcon({
        className: "",
        html: `<div style="width:14px;height:14px;border-radius:9999px;background:#4FA6D9;border:2px solid white;box-shadow:0 0 0 4px rgba(79,166,217,0.3);"></div>`,
        iconSize: [14, 14],
      });
      const marker = L.marker([cameraCoords.lat, cameraCoords.lng], { icon: cameraIcon }).addTo(map);
      marker.bindPopup(source.kind === "registry" ? source.title : "Camera");
      markersRef.current.push(marker);
    }

    for (const responder of responders) {
      const isSelected = responder.id === selectedResponderId;
      const icon = L.divIcon({
        className: "",
        html: `<div style="width:12px;height:12px;border-radius:9999px;background:${
          isSelected ? "#49A87A" : "#E08A3E"
        };border:2px solid white;"></div>`,
        iconSize: [12, 12],
      });
      const marker = L.marker([responder.lat, responder.lng], { icon }).addTo(map);
      marker.bindPopup(`${responder.name} — ${responder.unit}`);
      marker.on("click", () => onSelectResponder(responder.id));
      markersRef.current.push(marker);
    }
  }, [cameraCoords, responders, selectedResponderId, source, onSelectResponder]);

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface-1 border border-border-strong rounded-sm w-full max-w-4xl h-[80vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2 font-mono text-xs font-semibold text-text-primary tracking-wide">
            <Icons.Map className="w-4 h-4 text-accent" />
            GEOGRAPHIC MAP
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onRequestDispatch}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-white bg-sev-critical/20 border border-sev-critical/40 hover:bg-sev-critical/30 rounded-sm transition-colors"
            >
              <Icons.Radio className="w-3.5 h-3.5" />
              DISPATCH
            </button>
            <button onClick={onClose} className="text-text-tertiary hover:text-white">
              <Icons.X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 relative">
          <div ref={mapContainerRef} className="absolute inset-0" />

          {!cameraCoords && (
            <div className="absolute top-3 left-3 right-3 z-[500] px-3 py-2 text-xs font-mono text-text-secondary bg-surface-1/95 border border-border rounded-sm">
              This camera has no real geographic coordinates yet. Camera location will appear here once the Map API
              is integrated.
            </div>
          )}
          {responders.length === 0 && (
            <div className="absolute bottom-3 left-3 right-3 z-[500] px-3 py-2 text-xs font-mono text-text-secondary bg-surface-1/95 border border-border rounded-sm">
              No responder data available. Responder locations will appear here once the Map API is integrated.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
