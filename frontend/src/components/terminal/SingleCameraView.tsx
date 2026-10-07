import { useCallback, useRef, useState, type ReactNode, type RefObject } from "react";
import { submitAnalysis, getAnalysisStatus, getAnalysisResult } from "../../api/anomaly";
import { submitYoloDetect, submitYoloTrack, getYoloJobStatus, getYoloJobResult } from "../../api/yolo";
import { ApiError } from "../../api/client";
import { useJobPolling } from "../../lib/useJobPolling";
import { log } from "../../lib/logStore";
import { DetectionOverlay } from "../DetectionOverlay";
import { VideoPlayer } from "./VideoPlayer";
import { TemporalEvidenceTimeline } from "./TemporalEvidenceTimeline";
import type { AnalysisResult } from "../../types/anomaly";
import type { YoloJobResult, YoloMode } from "../../types/yolo";
import type { ResponderRecord } from "../../services/responderApi";
import type { ActiveSource } from "./types";
import type { JobHistoryEntry } from "./TerminalApp";
import { Icons } from "./icons";

type OverlayMode = "detections" | "tracking";

/**
 * Single-camera workspace. Real video playback of the actual selected
 * source; real analysis submission/polling/result rendering for both
 * backend engines (anomaly pipeline, YOLO26). No fabricated results —
 * every number shown comes directly from the backend's response.
 */
export function SingleCameraView({
  source,
  responders,
  selectedResponderId,
  onSelectResponder,
  onOpenMap,
  onDispatch,
  onJobCompleted,
}: {
  source: ActiveSource;
  responders: ResponderRecord[];
  selectedResponderId: string | null;
  onSelectResponder: (id: string | null) => void;
  onOpenMap: () => void;
  onDispatch: () => void;
  onJobCompleted: (entry: JobHistoryEntry) => void;
}) {
  const [rightTab, setRightTab] = useState<"chat" | "metrics">("metrics");
  const [latestResult, setLatestResult] = useState<AnalysisResult | YoloJobResult | null>(null);

  return (
    <div className="flex-1 flex overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden p-4 gap-3">
        <SourceHeader source={source} onOpenMap={onOpenMap} onDispatch={onDispatch} />

        <div className="relative flex-1 min-h-0 bg-surface-0 border border-border rounded-sm flex items-center justify-center overflow-hidden">
          {source.kind === "uploaded" ? (
            <UploadedWorkspace
              key={source.id}
              source={source}
              onJobCompleted={(entry) => {
                setLatestResult(entry);
                onJobCompleted(entry);
              }}
            />
          ) : (
            <NoVideoState />
          )}
        </div>
      </div>

      <aside className="w-80 shrink-0 border-l border-border bg-surface-1 flex flex-col overflow-hidden">
        <div className="flex border-b border-border shrink-0">
          <TabButton active={rightTab === "chat"} onClick={() => setRightTab("chat")} icon={<Icons.Bot className="w-3.5 h-3.5" />}>
            COPILOT
          </TabButton>
          <TabButton active={rightTab === "metrics"} onClick={() => setRightTab("metrics")} icon={<Icons.Zap className="w-3.5 h-3.5" />}>
            METRICS
          </TabButton>
        </div>

        <div className="flex-1 overflow-auto">
          {rightTab === "chat" ? (
            <CopilotPanelInline />
          ) : (
            <MetricsPanelInline
              responders={responders}
              selectedResponderId={selectedResponderId}
              onSelectResponder={onSelectResponder}
              result={latestResult}
            />
          )}
        </div>
      </aside>
    </div>
  );
}

function NoVideoState() {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <Icons.Video className="w-8 h-8 text-text-tertiary" />
      <div className="font-mono text-xs text-text-secondary">NO VIDEO SOURCE</div>
      <div className="text-[11px] text-text-tertiary max-w-[260px]">
        This camera has no uploaded video and no live stream configured.
      </div>
    </div>
  );
}

function SourceHeader({
  source,
  onOpenMap,
  onDispatch,
}: {
  source: ActiveSource;
  onOpenMap: () => void;
  onDispatch: () => void;
}) {
  const title = source.kind === "registry" ? source.title : source.file.name;
  const subtitle = source.kind === "registry" ? source.location : "Uploaded video source (not a live feed)";

  return (
    <div className="flex items-center justify-between shrink-0">
      <div>
        <div className="font-mono text-sm font-semibold text-white">{title}</div>
        <div className="text-[11px] text-text-tertiary">{subtitle}</div>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onOpenMap}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-text-secondary hover:text-white bg-surface-2 border border-border rounded-sm transition-colors"
        >
          <Icons.Map className="w-3.5 h-3.5" />
          MAP
        </button>
        <button
          onClick={onDispatch}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-white bg-sev-critical/20 border border-sev-critical/40 hover:bg-sev-critical/30 rounded-sm transition-colors"
        >
          <Icons.Radio className="w-3.5 h-3.5" />
          DISPATCH RESPONDER
        </button>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-[11px] font-mono font-semibold tracking-wide transition-colors ${
        active ? "text-accent border-b-2 border-accent bg-surface-2" : "text-text-tertiary hover:text-text-secondary"
      }`}
    >
      {icon}
      {children}
    </button>
  );
}

/** Owns the real File + its engine type, and the real analysis workflow
 * for that one file. Routes to the anomaly pipeline or YOLO26 depending
 * on which engine the operator picked at upload time. */
function UploadedWorkspace({
  source,
  onJobCompleted,
}: {
  source: Extract<ActiveSource, { kind: "uploaded" }>;
  onJobCompleted: (entry: JobHistoryEntry) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);

  return source.engineType === "anomaly" ? (
    <AnomalyWorkspace file={source.file} videoUrl={source.objectUrl} videoRef={videoRef} onJobCompleted={onJobCompleted} />
  ) : (
    <YoloWorkspace file={source.file} videoUrl={source.objectUrl} videoRef={videoRef} onJobCompleted={onJobCompleted} />
  );
}

function AnomalyWorkspace({
  file,
  videoUrl,
  videoRef,
  onJobCompleted,
}: {
  file: File;
  videoUrl: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  onJobCompleted: (entry: JobHistoryEntry) => void;
}) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const resultFetchedRef = useRef<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState<number | null>(null);

  const fetchStatus = useCallback((id: string) => getAnalysisStatus(id), []);
  const polling = useJobPolling<AnalysisResult>(jobId, fetchStatus);

  if (polling.phase === "completed" && jobId && resultFetchedRef.current !== jobId) {
    resultFetchedRef.current = jobId;
    getAnalysisResult(jobId)
      .then((full) => {
        setResult(full);
        onJobCompleted({ engine: "anomaly", ...full });
      })
      .catch((err) => {
        const message = err instanceof ApiError ? err.message : "Failed to fetch analysis result.";
        setSubmitError(message);
      });
  }

  const handleAnalyze = async () => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await submitAnalysis(file);
      setJobId(response.job_id);
      log("anomaly", "Analysis submitted", "JOB CREATED");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Analysis submission failed.";
      setSubmitError(message);
      log("anomaly", "Analysis submission failed", "FAILED");
    } finally {
      setSubmitting(false);
    }
  };

  const isBusy = submitting || polling.phase === "polling";

  return (
    <div className="relative w-full h-full flex flex-col gap-3">
      <div className="flex-1 min-h-0">
        <VideoPlayer
          key={videoUrl}
          videoUrl={videoUrl}
          videoRef={videoRef}
          onTimeUpdate={setCurrentTime}
          onDurationChange={setDuration}
        />
      </div>

      {result && (
        <TemporalEvidenceTimeline evidence={result.temporal_evidence} currentTime={currentTime} duration={duration} />
      )}

      <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-3 pointer-events-none">
        <div className="pointer-events-auto flex items-center gap-2">
          {!jobId && (
            <button
              disabled={isBusy}
              onClick={handleAnalyze}
              className="px-3 py-1.5 text-xs font-mono font-semibold text-white bg-accent/80 hover:bg-accent rounded-sm disabled:opacity-40 transition-colors"
            >
              ANALYZE VIDEO
            </button>
          )}
          {jobId && polling.phase === "polling" && (
            <StatusChip label={polling.job?.status === "processing" ? "PROCESSING" : "QUEUED"} tone="moderate" />
          )}
          {polling.phase === "failed" && <StatusChip label="FAILED" tone="critical" />}
          {polling.phase === "error" && <StatusChip label="ERROR" tone="critical" />}
          {result && polling.phase === "completed" && (
            <StatusChip
              label={result.anomaly_detected ? "ANOMALY DETECTED" : "CLEAR"}
              tone={result.anomaly_detected ? "critical" : "clear"}
            />
          )}
        </div>
      </div>

      {submitError && (
        <div className="absolute top-12 left-3 right-3 px-3 py-2 text-xs font-mono text-sev-critical bg-sev-critical/10 border border-sev-critical/30 rounded-sm">
          {submitError}
        </div>
      )}
      {polling.phase === "failed" && polling.job?.error && (
        <div className="absolute top-12 left-3 right-3 px-3 py-2 text-xs font-mono text-sev-critical bg-sev-critical/10 border border-sev-critical/30 rounded-sm">
          {polling.job.error}
        </div>
      )}
      {polling.phase === "error" && polling.errorMessage && (
        <div className="absolute top-12 left-3 right-3 px-3 py-2 text-xs font-mono text-sev-critical bg-sev-critical/10 border border-sev-critical/30 rounded-sm">
          {polling.errorMessage}
        </div>
      )}
    </div>
  );
}

function YoloWorkspace({
  file,
  videoUrl,
  videoRef,
  onJobCompleted,
}: {
  file: File;
  videoUrl: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  onJobCompleted: (entry: JobHistoryEntry) => void;
}) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<YoloJobResult | null>(null);
  const [overlayMode, setOverlayMode] = useState<OverlayMode>("detections");
  const resultFetchedRef = useRef<string | null>(null);

  const fetchStatus = useCallback((id: string) => getYoloJobStatus(id), []);
  const polling = useJobPolling<YoloJobResult>(jobId, fetchStatus);

  if (polling.phase === "completed" && jobId && resultFetchedRef.current !== jobId) {
    resultFetchedRef.current = jobId;
    getYoloJobResult(jobId)
      .then((full) => {
        setResult(full);
        onJobCompleted({ engine: "vision_yolo", ...full });
      })
      .catch((err) => {
        const message = err instanceof ApiError ? err.message : "Failed to fetch YOLO result.";
        setSubmitError(message);
      });
  }

  const submit = async (requestedMode: YoloMode) => {
    setSubmitting(true);
    setSubmitError(null);
    setOverlayMode(requestedMode === "track" ? "tracking" : "detections");
    try {
      const response = requestedMode === "detect" ? await submitYoloDetect(file) : await submitYoloTrack(file);
      setJobId(response.job_id);
      log("yolo", requestedMode === "detect" ? "Detection submitted" : "Tracking submitted", "JOB CREATED");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "YOLO submission failed.";
      setSubmitError(message);
      log("yolo", "Submission failed", "FAILED");
    } finally {
      setSubmitting(false);
    }
  };

  const isBusy = submitting || polling.phase === "polling";
  const hasTracks = (result?.tracks.length ?? 0) > 0;

  return (
    <div className="relative w-full h-full flex flex-col">
      <div className="flex-1 min-h-0">
        <VideoPlayer
          key={videoUrl}
          videoUrl={videoUrl}
          videoRef={videoRef}
          overlay={
            result && result.video ? (
              <DetectionOverlay
                videoRef={videoRef}
                detections={result.detections}
                videoWidth={result.video.width}
                videoHeight={result.video.height}
                mode={overlayMode}
              />
            ) : undefined
          }
        />
      </div>

      <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-3 pointer-events-none">
        <div className="pointer-events-auto flex items-center gap-2">
          {!jobId && (
            <>
              <button
                disabled={isBusy}
                onClick={() => submit("detect")}
                className="px-3 py-1.5 text-xs font-mono font-semibold text-white bg-accent/80 hover:bg-accent rounded-sm disabled:opacity-40 transition-colors"
              >
                DETECT OBJECTS
              </button>
              <button
                disabled={isBusy}
                onClick={() => submit("track")}
                className="px-3 py-1.5 text-xs font-mono font-semibold text-white bg-accent/80 hover:bg-accent rounded-sm disabled:opacity-40 transition-colors"
              >
                TRACK OBJECTS
              </button>
            </>
          )}
          {jobId && polling.phase === "polling" && (
            <StatusChip label={polling.job?.status === "processing" ? "PROCESSING" : "QUEUED"} tone="moderate" />
          )}
          {polling.phase === "failed" && <StatusChip label="FAILED" tone="critical" />}
          {polling.phase === "error" && <StatusChip label="ERROR" tone="critical" />}
          {result && result.detections.length > 0 && (
            <div className="flex items-center gap-1 rounded-sm border border-border p-0.5 bg-surface-1/90">
              <OverlayToggle label="Detections" active={overlayMode === "detections"} onClick={() => setOverlayMode("detections")} />
              <OverlayToggle label="Tracking" active={overlayMode === "tracking"} onClick={() => setOverlayMode("tracking")} disabled={!hasTracks} />
            </div>
          )}
        </div>
      </div>

      {submitError && (
        <div className="absolute top-12 left-3 right-3 px-3 py-2 text-xs font-mono text-sev-critical bg-sev-critical/10 border border-sev-critical/30 rounded-sm">
          {submitError}
        </div>
      )}
      {polling.phase === "failed" && polling.job?.error && (
        <div className="absolute top-12 left-3 right-3 px-3 py-2 text-xs font-mono text-sev-critical bg-sev-critical/10 border border-sev-critical/30 rounded-sm">
          {polling.job.error}
        </div>
      )}
      {polling.phase === "error" && polling.errorMessage && (
        <div className="absolute top-12 left-3 right-3 px-3 py-2 text-xs font-mono text-sev-critical bg-sev-critical/10 border border-sev-critical/30 rounded-sm">
          {polling.errorMessage}
        </div>
      )}
    </div>
  );
}

function OverlayToggle({ label, active, onClick, disabled }: { label: string; active: boolean; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-2 py-1 text-[11px] font-mono rounded-sm disabled:opacity-30 transition-colors ${
        active ? "bg-accent text-surface-0" : "text-text-secondary hover:text-white"
      }`}
    >
      {label}
    </button>
  );
}

function StatusChip({ label, tone }: { label: string; tone: "moderate" | "critical" | "clear" }) {
  const toneClass =
    tone === "critical"
      ? "bg-sev-critical/20 text-sev-critical border-sev-critical/40"
      : tone === "clear"
        ? "bg-sev-clear/20 text-sev-clear border-sev-clear/40"
        : "bg-sev-moderate/20 text-sev-moderate border-sev-moderate/40";
  return <div className={`px-2 py-1 text-[11px] font-mono rounded-sm border ${toneClass}`}>{label}</div>;
}

export function CopilotPanelInline() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-6 text-center h-full">
      <Icons.Bot className="w-8 h-8 text-text-tertiary" />
      <div className="font-mono text-xs font-semibold text-text-secondary">COPILOT NOT CONNECTED</div>
      <div className="text-[11px] text-text-tertiary max-w-[220px]">
        No AI service is currently configured. A real Copilot can be connected here once a backend endpoint exists.
      </div>
    </div>
  );
}

function isYoloResult(result: AnalysisResult | YoloJobResult): result is YoloJobResult {
  return "mode" in result;
}

function MetricsPanelInline({
  responders,
  selectedResponderId,
  onSelectResponder,
  result,
}: {
  responders: ResponderRecord[];
  selectedResponderId: string | null;
  onSelectResponder: (id: string | null) => void;
  result: AnalysisResult | YoloJobResult | null;
}) {
  return (
    <div className="p-3 flex flex-col gap-4">
      {result && (
        <div className="flex flex-col gap-2">
          <SectionLabel text="Latest result" />
          {isYoloResult(result) ? (
            <>
              <DataRow label="Mode" value={result.mode} />
              <DataRow label="Detections" value={String(result.detections.length)} />
              <DataRow label="Tracks" value={String(result.tracks.length)} />
              {result.summary && (
                <>
                  <DataRow label="Persons" value={String(result.summary.object_counts.persons)} />
                  <DataRow label="Vehicles" value={String(result.summary.object_counts.vehicles)} />
                </>
              )}
              {result.performance && (
                <DataRow label="Processing time" value={`${result.performance.processing_time_seconds.toFixed(2)}s`} />
              )}
            </>
          ) : (
            <>
              <DataRow label="Status" value={result.anomaly_detected ? "Anomaly detected" : "Clear"} />
              {result.anomaly_probability !== null && (
                <DataRow label="Probability" value={`${(result.anomaly_probability * 100).toFixed(1)}%`} />
              )}
              {result.likely_action && <DataRow label="Likely action" value={result.likely_action} />}
              {result.action_confidence !== null && (
                <DataRow label="Confidence" value={`${(result.action_confidence * 100).toFixed(1)}%`} />
              )}
              {result.processing_time_seconds !== null && (
                <DataRow label="Processing time" value={`${result.processing_time_seconds.toFixed(2)}s`} />
              )}
            </>
          )}
        </div>
      )}

      <div className="flex flex-col gap-2">
        <SectionLabel text="Nearby responders" />
        {responders.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Icons.Radio className="w-6 h-6 text-text-tertiary" />
            <div className="font-mono text-[11px] font-semibold text-text-secondary">NO RESPONDERS AVAILABLE</div>
            <div className="text-[11px] text-text-tertiary max-w-[200px]">
              Responder data requires the Map API integration.
            </div>
          </div>
        ) : (
          responders.map((r) => (
            <button
              key={r.id}
              onClick={() => onSelectResponder(r.id)}
              className={`text-left px-3 py-2 rounded-sm border text-xs font-mono transition-colors ${
                selectedResponderId === r.id ? "border-accent bg-accent/10" : "border-border hover:border-border-strong"
              }`}
            >
              <div className="text-white font-semibold">{r.name}</div>
              <div className="text-text-tertiary">{r.unit}</div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function SectionLabel({ text }: { text: string }) {
  return <div className="text-[11px] font-mono font-semibold text-text-tertiary tracking-wide">{text}</div>;
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-xs text-text-tertiary">{label}</span>
      <span className="truncate font-mono text-xs text-text-secondary">{value}</span>
    </div>
  );
}
