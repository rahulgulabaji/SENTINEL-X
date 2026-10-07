import { useState } from "react";
import type { JobHistoryEntry } from "./TerminalApp";
import { Icons } from "./icons";

/** Shows the real backend result object for a completed job, exactly as
 * received — no reformatting that could misrepresent the data. */
export function JsonLogModal({ entry, onClose }: { entry: JobHistoryEntry; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const json = JSON.stringify(entry, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface-1 border border-border-strong rounded-sm w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <div className="font-mono text-xs font-semibold text-text-primary tracking-wide">
            RAW RESULT — {entry.engine === "anomaly" ? "ANOMALY PIPELINE" : "YOLO26"} · {entry.job_id}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 px-2 py-1 text-[11px] font-mono text-text-secondary hover:text-white bg-surface-2 border border-border rounded-sm"
            >
              {copied ? <Icons.Check className="w-3 h-3 text-sev-clear" /> : <Icons.Copy className="w-3 h-3" />}
              {copied ? "COPIED" : "COPY"}
            </button>
            <button onClick={onClose} className="text-text-tertiary hover:text-white">
              <Icons.X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <pre className="p-4 overflow-auto text-[11px] font-mono text-text-secondary whitespace-pre-wrap break-all">
          {json}
        </pre>
      </div>
    </div>
  );
}
