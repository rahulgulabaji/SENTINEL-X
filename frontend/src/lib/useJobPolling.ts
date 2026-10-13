import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";

/** Shared shape every pollable job result has in common — both
 * AnalysisResult and YoloJobResult satisfy this. */
export interface PollableJob {
  status: "queued" | "processing" | "completed" | "failed";
  error?: string | null;
}

export type PollingPhase = "idle" | "polling" | "completed" | "failed" | "error";

interface UseJobPollingState<T extends PollableJob> {
  phase: PollingPhase;
  job: T | null;
  /** Set when phase === "error" — a transport/HTTP problem, distinct from
   * the backend reporting status: "failed" with its own `error` field. */
  errorMessage: string | null;
}

const POLL_INTERVAL_MS = 2500;

/**
 * Polls `fetchStatus(jobId)` every ~2.5s until the job reaches a terminal
 * backend state (completed/failed), or a transport/HTTP error occurs.
 * Never fabricates progress — the returned `job` is exactly what the
 * backend last reported.
 */
export function useJobPolling<T extends PollableJob>(
  jobId: string | null,
  fetchStatus: (jobId: string) => Promise<T>,
) {
  const [state, setState] = useState<UseJobPollingState<T>>({
    phase: "idle",
    job: null,
    errorMessage: null,
  });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeJobIdRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    activeJobIdRef.current = jobId;
    stop();

    if (!jobId) {
      setState({ phase: "idle", job: null, errorMessage: null });
      return;
    }

    setState({ phase: "polling", job: null, errorMessage: null });

    const poll = async () => {
      try {
        const job = await fetchStatus(jobId);
        // Guard against a stale poll resolving after a newer job started.
        if (activeJobIdRef.current !== jobId) return;

        if (job.status === "completed") {
          setState({ phase: "completed", job, errorMessage: null });
          return;
        }
        if (job.status === "failed") {
          setState({ phase: "failed", job, errorMessage: null });
          return;
        }
        setState({ phase: "polling", job, errorMessage: null });
        timerRef.current = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (activeJobIdRef.current !== jobId) return;
        const message =
          err instanceof ApiError ? err.message : "Unexpected error while polling job status.";
        setState({ phase: "error", job: null, errorMessage: message });
      }
    };

    void poll();

    return () => {
      stop();
    };
  }, [jobId, fetchStatus, stop]);

  return state;
}
