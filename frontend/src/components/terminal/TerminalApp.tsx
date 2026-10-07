import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { getAppHealth } from "../../api/health";
import { log } from "../../lib/logStore";
import { useLog } from "../../lib/useLog";
import { getCameras, type CameraRecord } from "../../services/cameraApi";
import { getResponders, type ResponderRecord } from "../../services/responderApi";
import type { AnalysisResult } from "../../types/anomaly";
import type { YoloJobResult } from "../../types/yolo";
import type { ActiveSource, TerminalView } from "./types";
import { Icons } from "./icons";
import { LandingView } from "./LandingView";
import { CameraMatrix } from "./CameraMatrix";
import { SingleCameraView } from "./SingleCameraView";
import { AuditTrailView } from "./AuditTrailView";
import { MapModal } from "./MapModal";
import { DispatchModal } from "./DispatchModal";
import { SettingsModal } from "./SettingsModal";
import { JsonLogModal } from "./JsonLogModal";

export type JobHistoryEntry =
  | ({ engine: "anomaly" } & AnalysisResult)
  | ({ engine: "vision_yolo" } & YoloJobResult);

/** Backend connectivity state, polled from the real /api/health endpoint.
 * Never falls back to a simulated/offline-engine mode — if the backend is
 * unreachable, the UI shows that honestly. */
export interface BackendHealth {
  connected: boolean;
  checking: boolean;
  inferenceReady: boolean | null;
}

/** Top-level Tactical Terminal shell — ported from the approved HTML
 * reference. Internal view state (landing/grid/single/logs) matches the
 * reference's own navigation model exactly; this is deliberately not
 * split into router routes, since the approved UX has modals overlay any
 * view and tab-switch instantly with no navigation. */
export function TerminalApp() {
  const [view, setView] = useState<TerminalView>("landing");
  const [health, setHealth] = useState<BackendHealth>({ connected: false, checking: true, inferenceReady: null });
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showMapModal, setShowMapModal] = useState(false);
  const [showNotifyModal, setShowNotifyModal] = useState(false);
  const [selectedLogItem, setSelectedLogItem] = useState<JobHistoryEntry | null>(null);

  const [cameras, setCameras] = useState<CameraRecord[]>([]);
  const [responders, setResponders] = useState<ResponderRecord[]>([]);
  const [activeSource, setActiveSource] = useState<ActiveSource | null>(null);
  const [selectedResponderId, setSelectedResponderId] = useState<string | null>(null);

  const [jobHistory, setJobHistory] = useState<JobHistoryEntry[]>([]);

  const auditEntries = useLog();

  const checkHealth = useCallback(async () => {
    setHealth((prev) => ({ ...prev, checking: true }));
    try {
      const data = await getAppHealth();
      setHealth({ connected: true, checking: false, inferenceReady: data.inference_ready });
    } catch {
      setHealth({ connected: false, checking: false, inferenceReady: null });
    }
  }, []);

  useEffect(() => {
    log("system", "Tactical Terminal started", "SESSION START");
    void checkHealth();
    const timer = setInterval(checkHealth, 10000);
    return () => clearInterval(timer);
  }, [checkHealth]);

  // Track connect/disconnect transitions for the audit trail — logged
  // once per real transition, not on every poll tick.
  useEffect(() => {
    if (health.checking) return;
    log("system", health.connected ? "Backend connected" : "Backend unreachable", health.connected ? "ONLINE" : "OFFLINE");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [health.connected, health.checking]);

  useEffect(() => {
    void getCameras().then(setCameras);
    void getResponders().then(setResponders);
  }, []);

  const selectedResponder = useMemo(
    () => responders.find((r) => r.id === selectedResponderId) ?? null,
    [responders, selectedResponderId],
  );

  const handleOpenSource = (source: ActiveSource) => {
    setActiveSource(source);
    setView("single");
  };

  const handleJobCompleted = (entry: JobHistoryEntry) => {
    setJobHistory((prev) => [entry, ...prev]);
    const label = entry.engine === "anomaly" ? entry.likely_action ?? "Analysis complete" : "YOLO job complete";
    log(entry.engine === "anomaly" ? "anomaly" : "yolo", label, "COMPLETED", entry);
  };

  return (
    <div className="min-h-screen bg-surface-0 text-text-primary flex flex-col font-sans antialiased selection:bg-accent/30">
      <TerminalHeader
        view={view}
        setView={setView}
        activeSource={activeSource}
        cameraCount={cameras.length}
        jobHistoryCount={jobHistory.length}
        health={health}
        onOpenSettings={() => setShowSettingsModal(true)}
      />

      <main className="flex-1 flex flex-col overflow-hidden">
        {view === "landing" && (
          <LandingView
            cameraCount={cameras.length}
            onEnterMatrix={() => setView("grid")}
            onSourceUploaded={handleOpenSource}
          />
        )}

        {view === "grid" && (
          <CameraMatrix cameras={cameras} onOpenSource={handleOpenSource} />
        )}

        {view === "single" && activeSource && (
          <SingleCameraView
            source={activeSource}
            responders={responders}
            selectedResponderId={selectedResponderId}
            onSelectResponder={setSelectedResponderId}
            onOpenMap={() => setShowMapModal(true)}
            onDispatch={() => {
              setShowMapModal(true);
              setShowNotifyModal(true);
            }}
            onJobCompleted={handleJobCompleted}
          />
        )}

        {view === "logs" && (
          <AuditTrailView
            jobHistory={jobHistory}
            auditEntries={auditEntries}
            onInspect={setSelectedLogItem}
          />
        )}
      </main>

      {showMapModal && activeSource && (
        <MapModal
          source={activeSource}
          responders={responders}
          selectedResponderId={selectedResponderId}
          onSelectResponder={setSelectedResponderId}
          onClose={() => setShowMapModal(false)}
          onRequestDispatch={() => setShowNotifyModal(true)}
        />
      )}

      {showNotifyModal && (
        <DispatchModal
          source={activeSource}
          responder={selectedResponder}
          onClose={() => setShowNotifyModal(false)}
        />
      )}

      {showSettingsModal && (
        <SettingsModal health={health} onRefresh={checkHealth} onClose={() => setShowSettingsModal(false)} />
      )}

      {selectedLogItem && (
        <JsonLogModal entry={selectedLogItem} onClose={() => setSelectedLogItem(null)} />
      )}
    </div>
  );
}

function TerminalHeader({
  view,
  setView,
  activeSource,
  cameraCount,
  jobHistoryCount,
  health,
  onOpenSettings,
}: {
  view: TerminalView;
  setView: (v: TerminalView) => void;
  activeSource: ActiveSource | null;
  cameraCount: number;
  jobHistoryCount: number;
  health: BackendHealth;
  onOpenSettings: () => void;
}) {
  return (
    <header className="h-14 bg-surface-1 border-b border-border px-4 flex items-center justify-between shrink-0 z-40">
      <div className="flex items-center gap-4">
        <button onClick={() => setView("landing")} className="flex items-center gap-2.5 text-left focus:outline-none group">
          <div className="w-8 h-8 rounded-sm bg-accent/10 border border-accent/30 flex items-center justify-center text-accent group-hover:bg-accent group-hover:text-white transition-all">
            <Icons.Shield className="w-4 h-4" />
          </div>
          <div>
            <div className="font-mono font-bold text-xs tracking-wider text-white flex items-center gap-2">
              <span>SENTINEL-X</span>
              <span className="text-[10px] text-accent bg-accent/10 border border-accent/20 px-1.5 py-0.2 rounded-sm font-normal">
                v2.4 TACTICAL
              </span>
            </div>
            <div className="text-[10px] text-text-tertiary font-mono">Camera Vision &amp; Dispatch Terminal</div>
          </div>
        </button>

        <div className="h-4 w-[1px] bg-border hidden sm:block"></div>

        <nav className="hidden sm:flex items-center gap-1 text-xs font-mono">
          <NavButton active={view === "landing"} onClick={() => setView("landing")} icon={<Icons.Home className="w-3.5 h-3.5" />}>
            OVERVIEW
          </NavButton>
          <NavButton active={view === "grid"} onClick={() => setView("grid")} icon={<Icons.Grid className="w-3.5 h-3.5" />}>
            CAMERA MATRIX ({cameraCount})
          </NavButton>
          {view === "single" && activeSource && (
            <button className="px-3 py-1.5 rounded-sm bg-accent/20 text-accent font-semibold border border-accent/40 flex items-center gap-1.5">
              <Icons.Video className="w-3.5 h-3.5" />
              <span>CHANNEL: {activeSource.kind === "registry" ? activeSource.id : activeSource.file.name}</span>
            </button>
          )}
          <NavButton active={view === "logs"} onClick={() => setView("logs")}>
            AUDIT TRAIL ({jobHistoryCount})
          </NavButton>
        </nav>
      </div>

      <div className="flex items-center gap-3 font-mono text-xs">
        <div
          onClick={onOpenSettings}
          className={`flex items-center gap-2 px-2.5 py-1 rounded-sm border cursor-pointer transition-all ${
            health.connected
              ? "bg-sev-clear/10 border-sev-clear/30 text-sev-clear"
              : "bg-sev-critical/10 border-sev-critical/30 text-sev-critical"
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${health.connected ? "bg-sev-clear animate-pulse" : "bg-sev-critical"}`}></span>
          <span className="text-[11px] font-semibold tracking-wide">
            {health.checking ? "PINGING..." : health.connected ? "API CONNECTED" : "API OFFLINE"}
          </span>
        </div>

        <button
          onClick={onOpenSettings}
          className="p-1.5 text-text-secondary hover:text-white bg-surface-2 border border-border rounded-sm transition-colors"
        >
          <Icons.Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}

function NavButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 rounded-sm transition-colors flex items-center gap-1.5 ${
        active ? "bg-surface-2 text-white font-semibold border border-border-strong" : "text-text-secondary hover:text-text-primary hover:bg-surface-1"
      }`}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}
