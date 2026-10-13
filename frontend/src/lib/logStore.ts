/**
 * Session event log — a dedicated, minimal store for real frontend/backend
 * events (not a general state manager). Entries are only ever created by
 * explicit calls from app code at the moment a real event happens (backend
 * connected, job submitted, job completed, etc.) — never pre-seeded,
 * never fabricated.
 *
 * Deliberately framework-agnostic (no React import) and swappable: a
 * future backend-persisted log would replace the `log()` call sites with
 * a POST to a /logs endpoint and `getEntries()`/`subscribe()` with a fetch,
 * without changing how callers in pages/components invoke this module.
 */

export type LogType = "system" | "anomaly" | "yolo";

export interface LogEntry {
  id: string;
  time: string; // HH:MM:SS, local
  type: LogType;
  event: string;
  status: string;
  /** Optional real payload for inspection (e.g. a completed job's full
   * result). Only ever the actual object passed by the caller — never
   * synthesized here. */
  detail?: unknown;
}

let entries: LogEntry[] = [];
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", { hour12: false });
}

export function log(type: LogType, event: string, status: string, detail?: unknown): LogEntry {
  const entry: LogEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    time: formatTime(new Date()),
    type,
    event,
    status,
    detail,
  };
  entries = [entry, ...entries];
  notify();
  return entry;
}

export function getEntries(): LogEntry[] {
  return entries;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function clearLog(): void {
  entries = [];
  notify();
}
