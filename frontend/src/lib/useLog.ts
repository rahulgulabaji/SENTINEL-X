import { useEffect, useState } from "react";
import { getEntries, subscribe, type LogEntry } from "./logStore";

/** Subscribes a component to the session log store, re-rendering on every
 * new entry. */
export function useLog(): LogEntry[] {
  const [entries, setEntries] = useState<LogEntry[]>(() => getEntries());

  useEffect(() => {
    return subscribe(() => setEntries(getEntries()));
  }, []);

  return entries;
}
