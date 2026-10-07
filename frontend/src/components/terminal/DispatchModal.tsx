import { useState } from "react";
import { sendDispatchNotification, type DispatchNotificationResult } from "../../services/notificationApi";
import type { ResponderRecord } from "../../services/responderApi";
import type { ActiveSource } from "./types";
import { Icons } from "./icons";

/**
 * Dispatch/SMS notification modal. Visual chrome preserved from the
 * approved reference. The backend has no notification mechanism today —
 * sendDispatchNotification always resolves to a "not_configured" result
 * with no network call, and that is exactly what this modal shows. There
 * is no path to a fabricated "sent" state.
 */
export function DispatchModal({
  source,
  responder,
  onClose,
}: {
  source: ActiveSource | null;
  responder: ResponderRecord | null;
  onClose: () => void;
}) {
  const [message, setMessage] = useState("Possible incident detected. Please respond.");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<DispatchNotificationResult | null>(null);

  const handleSend = async () => {
    setSending(true);
    try {
      const outcome = await sendDispatchNotification({
        jobId: source?.kind === "registry" ? source.id : "uploaded-video",
        responderId: responder?.id ?? "",
        message,
        phone: responder?.phone ?? "",
      });
      setResult(outcome);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-[60] flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface-1 border border-border-strong rounded-sm w-full max-w-md shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 font-mono text-xs font-semibold text-text-primary tracking-wide">
            <Icons.Radio className="w-4 h-4 text-sev-critical" />
            DISPATCH RESPONDER
          </div>
          <button onClick={onClose} className="text-text-tertiary hover:text-white">
            <Icons.X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 flex flex-col gap-3 text-xs font-mono">
          <div>
            <div className="text-text-tertiary mb-1">RESPONDER</div>
            {responder ? (
              <div className="px-3 py-2 bg-surface-2 border border-border rounded-sm text-text-primary">
                {responder.name} — {responder.unit}
              </div>
            ) : (
              <div className="px-3 py-2 bg-surface-2 border border-border rounded-sm text-text-tertiary">
                No responder selected. Responder data requires the Map API integration.
              </div>
            )}
          </div>

          <div>
            <div className="text-text-tertiary mb-1">MESSAGE</div>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-sm text-text-primary resize-none focus:outline-none focus:border-accent"
            />
          </div>

          {result && (
            <div
              className={`px-3 py-2 rounded-sm border flex items-start gap-2 ${
                result.status === "not_configured"
                  ? "bg-sev-moderate/10 border-sev-moderate/30 text-sev-moderate"
                  : ""
              }`}
            >
              <Icons.AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold">NOT CONFIGURED</div>
                <div className="text-[11px] mt-0.5">{result.reason}</div>
              </div>
            </div>
          )}

          <button
            onClick={handleSend}
            disabled={sending}
            className="w-full py-2 rounded-sm bg-sev-critical/20 border border-sev-critical/40 text-white hover:bg-sev-critical/30 disabled:opacity-50 transition-colors"
          >
            {sending ? "SENDING..." : "SEND DISPATCH"}
          </button>
        </div>
      </div>
    </div>
  );
}
