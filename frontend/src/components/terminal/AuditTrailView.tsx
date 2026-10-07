import type { LogEntry } from "../../lib/logStore";
import type { JobHistoryEntry } from "./TerminalApp";
import { Icons } from "./icons";

/**
 * Audit trail: a real job-history table (one row per completed backend
 * job) plus the real session event log underneath. Both are populated
 * exclusively by real events — no synthetic rows.
 */
export function AuditTrailView({
  jobHistory,
  auditEntries,
  onInspect,
}: {
  jobHistory: JobHistoryEntry[];
  auditEntries: LogEntry[];
  onInspect: (entry: JobHistoryEntry) => void;
}) {
  return (
    <div className="flex-1 overflow-auto p-4 flex flex-col gap-6 max-w-5xl mx-auto w-full">
      <section>
        <div className="font-mono text-xs font-semibold text-text-primary tracking-wide mb-2">JOB HISTORY</div>
        {jobHistory.length === 0 ? (
          <EmptyPanel text="No completed jobs yet this session." />
        ) : (
          <div className="border border-border rounded-sm overflow-hidden">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="bg-surface-2 text-text-tertiary">
                  <th className="px-3 py-2">JOB ID</th>
                  <th className="px-3 py-2">ENGINE</th>
                  <th className="px-3 py-2">RESULT</th>
                  <th className="px-3 py-2">TIME</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {jobHistory.map((entry) => (
                  <tr key={entry.job_id} className="border-t border-border">
                    <td className="px-3 py-2 text-text-secondary truncate max-w-[160px]">{entry.job_id}</td>
                    <td className="px-3 py-2 text-text-secondary">
                      {entry.engine === "anomaly" ? "ANOMALY" : `YOLO26 (${entry.mode.toUpperCase()})`}
                    </td>
                    <td className="px-3 py-2 text-text-primary">
                      {entry.engine === "anomaly"
                        ? entry.anomaly_detected
                          ? `Anomaly: ${entry.likely_action ?? "unspecified"}`
                          : "Clear"
                        : `${entry.detections.length} detections, ${entry.tracks.length} tracks`}
                    </td>
                    <td className="px-3 py-2 text-text-tertiary">{entry.completed_at ?? "—"}</td>
                    <td className="px-3 py-2 text-right">
                      <button
                        onClick={() => onInspect(entry)}
                        className="text-accent hover:underline"
                      >
                        Inspect JSON
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <div className="font-mono text-xs font-semibold text-text-primary tracking-wide mb-2">SESSION EVENTS</div>
        {auditEntries.length === 0 ? (
          <EmptyPanel text="No events recorded yet this session." />
        ) : (
          <div className="border border-border rounded-sm overflow-hidden">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="bg-surface-2 text-text-tertiary">
                  <th className="px-3 py-2 w-20">TIME</th>
                  <th className="px-3 py-2 w-20">TYPE</th>
                  <th className="px-3 py-2">EVENT</th>
                  <th className="px-3 py-2 w-32">STATUS</th>
                </tr>
              </thead>
              <tbody>
                {auditEntries.map((entry) => (
                  <tr key={entry.id} className="border-t border-border">
                    <td className="px-3 py-2 text-text-secondary">{entry.time}</td>
                    <td className="px-3 py-2 text-text-secondary">{entry.type.toUpperCase()}</td>
                    <td className="px-3 py-2 text-text-primary">{entry.event}</td>
                    <td className="px-3 py-2 text-accent">{entry.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function EmptyPanel({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center border border-dashed border-border rounded-sm">
      <Icons.Grid className="w-5 h-5 text-text-tertiary" />
      <div className="text-xs text-text-secondary">{text}</div>
    </div>
  );
}
