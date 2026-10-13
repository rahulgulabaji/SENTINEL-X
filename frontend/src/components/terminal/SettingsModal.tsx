import { API_BASE_URL } from "../../api/client";
import type { BackendHealth } from "./TerminalApp";
import { Icons } from "./icons";

/**
 * Settings modal — visual chrome preserved from the approved reference,
 * but the editable-backend-URL field and the simulated-engine toggle are
 * removed: the backend URL is real configuration (VITE_API_BASE_URL),
 * read-only here, and there is no simulated inference mode to toggle.
 */
export function SettingsModal({
  health,
  onRefresh,
  onClose,
}: {
  health: BackendHealth;
  onRefresh: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-surface-1 border border-border-strong rounded-sm w-full max-w-md shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 font-mono text-xs font-semibold text-text-primary tracking-wide">
            <Icons.Settings className="w-4 h-4 text-accent" />
            SYSTEM CONFIGURATION
          </div>
          <button onClick={onClose} className="text-text-tertiary hover:text-white">
            <Icons.X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 flex flex-col gap-4 text-xs font-mono">
          <div>
            <div className="text-text-tertiary mb-1">BACKEND API ENDPOINT</div>
            <div className="px-3 py-2 bg-surface-2 border border-border rounded-sm text-text-secondary">
              {API_BASE_URL}
            </div>
            <div className="text-[10px] text-text-tertiary mt-1">
              Configured via VITE_API_BASE_URL at build time. Not editable here.
            </div>
          </div>

          <div>
            <div className="text-text-tertiary mb-1">CONNECTION STATUS</div>
            <div
              className={`flex items-center gap-2 px-3 py-2 rounded-sm border ${
                health.connected ? "bg-sev-clear/10 border-sev-clear/30 text-sev-clear" : "bg-sev-critical/10 border-sev-critical/30 text-sev-critical"
              }`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${health.connected ? "bg-sev-clear" : "bg-sev-critical"}`}></span>
              {health.checking ? "CHECKING..." : health.connected ? "CONNECTED" : "UNREACHABLE"}
            </div>
          </div>

          {health.connected && (
            <div>
              <div className="text-text-tertiary mb-1">INFERENCE PIPELINE</div>
              <div className="px-3 py-2 bg-surface-2 border border-border rounded-sm text-text-secondary">
                {health.inferenceReady ? "Loaded (I3D + Stage 1 + Stage 2)" : "Not loaded"}
              </div>
            </div>
          )}

          <button
            onClick={onRefresh}
            className="w-full py-2 rounded-sm bg-surface-2 border border-border-strong text-text-primary hover:bg-surface-3 transition-colors"
          >
            RE-CHECK CONNECTION
          </button>
        </div>
      </div>
    </div>
  );
}
