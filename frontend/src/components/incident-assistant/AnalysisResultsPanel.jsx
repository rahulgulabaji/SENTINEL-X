import React from 'react';
import { Icons } from '../../App';

/**
 * The "30% STRUCTURED INTELLIGENCE PANEL" from the Analysis view --
 * extracted verbatim out of App.jsx (behavior-preserving extraction only,
 * no visual/behavioral change) so the new AI Incident Assistant tabs can
 * sit alongside it without App.jsx growing further. Every prop here is
 * the exact same state App.jsx already owned and passed inline before
 * this extraction; this component owns no state of its own.
 */
export default function AnalysisResultsPanel({
  activeJob,
  duration,
  currentTime,
  hasEncounteredEvidence,
  lastEvidenceWindow,
  attentionHUD,
  selectedSource,
  openDispatchModal,
}) {
  return (
    <div className="flex flex-col gap-4 font-mono text-xs">

      <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
        <h3 className="font-bold text-white uppercase tracking-wider flex items-center gap-2">
          <Icons.Layers className="w-4 h-4 text-blue-400" />
          <span>INTELLIGENCE PANEL</span>
          {activeJob?.result?.simulated && (
            <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 border border-amber-500/40 rounded-sm text-[9px] font-bold">
              SIMULATED -- NOT A REAL BACKEND RESULT
            </span>
          )}
        </h3>
        <span className="text-[10px] text-slate-500">
          {activeJob ? activeJob.status.toUpperCase() : 'STANDBY'}
        </span>
      </div>

      {/* STATE 1: BEFORE ANALYSIS (READY FOR ANALYSIS) */}
      {!activeJob && (
        <div className="space-y-4">
          <div className="p-3.5 rounded-sm border bg-[#11131A] border-[#232838] space-y-2">
            <div className="flex items-center gap-2 text-blue-400 font-bold text-xs">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
              <span>READY FOR ANALYSIS</span>
            </div>
            <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
              Video source is loaded. Playing the video will automatically submit an inference job and classify threat telemetry.
            </p>
          </div>

          <div className="bg-[#11131A] p-3.5 rounded-sm border border-[#1E2232] space-y-2 text-[11px]">
            <span className="text-[10px] text-slate-500 uppercase block font-bold">PIPELINE STANDBY</span>
            <div className="flex justify-between text-slate-400">
              <span>I3D Backbone:</span>
              <span className="text-slate-300 font-mono">STANDBY</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Stage 1 Detector:</span>
              <span className="text-slate-300 font-mono">STANDBY</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Stage 2 Classifier:</span>
              <span className="text-slate-300 font-mono">STANDBY</span>
            </div>
          </div>
        </div>
      )}

      {/* STATE 2: ANALYSIS IN PROGRESS (QUEUED / PROCESSING) */}
      {activeJob && (activeJob.status === 'queued' || activeJob.status === 'processing') && (
        <div className="space-y-4">
          <div className="p-3.5 rounded-sm border bg-blue-500/10 border-blue-500/30 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-blue-400 font-bold text-xs">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping"></span>
                <span>ANALYSIS IN PROGRESS</span>
              </div>
              <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded-sm uppercase font-bold">
                {activeJob.status}
              </span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">
              JOB ID: <strong className="text-slate-200">{activeJob.jobId}</strong>
            </div>
          </div>

          <div className="bg-[#11131A] p-3.5 rounded-sm border border-[#1E2232] space-y-2.5 text-[11px]">
            <span className="text-[10px] text-slate-500 uppercase block font-bold">EXECUTION PIPELINE</span>

            <div className="flex items-center justify-between text-slate-300">
              <span className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
                <span>I3D Feature Extraction</span>
              </span>
              <span className="text-blue-400 font-mono text-[10px]">Processing</span>
            </div>

            <div className="flex items-center justify-between text-slate-300">
              <span className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
                <span>Stage 1 Binary Detector</span>
              </span>
              <span className="text-blue-400 font-mono text-[10px]">Evaluating</span>
            </div>

            <div className="flex items-center justify-between text-slate-300">
              <span className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-500"></span>
                <span>Stage 2 Action Classifier</span>
              </span>
              <span className="text-slate-500 font-mono text-[10px]">Sequenced</span>
            </div>
          </div>

          <div className="p-3 bg-[#11131A] rounded-sm border border-[#1E2232] flex items-center gap-3">
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0"></div>
            <div className="text-[11px] text-slate-400 font-sans">
              Video playback continues uninterrupted while neural models compute inference in the background.
            </div>
          </div>
        </div>
      )}

      {/* STEP 2E (v3) FIX: non-anomaly result must NOT be declared
          "CLEAR" the instant the backend finishes -- backend wall-
          clock processing time is not a video timestamp. The whole
          video has only actually been confirmed clear once
          playback itself has reached (or passed) its end. Gated on
          currentTime >= duration - small tolerance, same real
          currentTime/duration this component already tracks --
          no second clock, no fabricated per-frame result. */}
      {activeJob && activeJob.status === 'completed' && activeJob.system === 'anomaly' && activeJob.result &&
        !(activeJob.result.anomaly_detected || (activeJob.result.anomaly_probability && activeJob.result.anomaly_probability > 0.5)) &&
        duration != null && currentTime >= duration - 0.5 && (
        <div className="p-3 rounded-sm border bg-emerald-500/10 border-emerald-500/30 text-emerald-400">
          <div className="text-[10px] uppercase text-slate-400">ANOMALY STATUS</div>
          <div className="text-base font-bold uppercase mt-0.5">NORMAL ACTIVITY / CLEAR</div>
        </div>
      )}

      {/* STEP 2E (v3) FIX: neutral state while a non-anomaly result
          has arrived but playback hasn't reached the end yet --
          the timeline's green reached/dark unreached track is the
          primary feedback here, this is just the Intelligence
          Panel's matching neutral text. */}
      {activeJob && activeJob.status === 'completed' && activeJob.system === 'anomaly' && activeJob.result &&
        !(activeJob.result.anomaly_detected || (activeJob.result.anomaly_probability && activeJob.result.anomaly_probability > 0.5)) &&
        !(duration != null && currentTime >= duration - 0.5) && (
        <div className="p-3 rounded-sm border bg-[#11131A] border-[#1E2232] text-blue-400 space-y-1">
          <div className="flex items-center gap-2 text-[10px] uppercase text-slate-400">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
            <span>ANALYSIS IN PROGRESS</span>
          </div>
          <div className="text-xs font-sans text-slate-300 leading-relaxed">
            No abnormal activity found so far. Final result confirms once playback reaches the end of the video.
          </div>
        </div>
      )}

      {/* STEP 2D: NEUTRAL "ANALYSIS READY" STATE.
          Backend result has arrived, but no qualifying evidence
          window has EVER been reached yet for this job
          (hasEncounteredEvidence). Unlike Step 2C, this does NOT
          re-show once an incident has been found -- it is a
          one-way gate into STATE 3 below. */}
      {activeJob && activeJob.status === 'completed' && activeJob.system === 'anomaly' && activeJob.result &&
        activeJob.result.anomaly_detected && !hasEncounteredEvidence && (
        <div className="space-y-4">
          <div className="p-3 rounded-sm border bg-[#11131A] border-blue-500/30 text-blue-400 space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase text-slate-400">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400"></span>
              <span>ANALYSIS READY</span>
            </div>
            <div className="text-xs font-sans text-slate-300 leading-relaxed">
              Temporal evidence will activate when playback reaches the evidence window.
            </div>
          </div>
        </div>
      )}

      {/* STEP 2D: STATE 3 -- INCIDENT DETECTED. Once latched via
          hasEncounteredEvidence, this panel stays mounted and
          stable for the rest of this job's lifetime -- it never
          reverts to ANALYSIS READY again, even as currentTime
          crosses in and out of evidence windows. Only the small
          temporal status line (ACTIVE NOW / EVIDENCE WINDOW
          PASSED) changes with attentionHUD.visible. */}
      {activeJob && activeJob.status === 'completed' && activeJob.system === 'anomaly' && activeJob.result && hasEncounteredEvidence && (
        <div className="space-y-4">

          {/* Anomaly Status Badge */}
          <div className="p-3 rounded-sm border bg-rose-500/10 border-rose-500/30 text-rose-400">
            <div className="text-[10px] uppercase text-slate-400">ANOMALY STATUS</div>
            <div className="text-base font-bold uppercase mt-0.5">INCIDENT DETECTED</div>
          </div>

          {/* STEP 2D: persistent temporal evidence status -- the
              only part of this panel that reacts to currentTime. */}
          {lastEvidenceWindow && (
            <div className={`p-2.5 rounded-sm border text-[11px] font-mono ${
              attentionHUD.visible
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                : 'bg-[#11131A] border-[#1E2232] text-slate-400'
            }`}>
              <div className="text-[9px] uppercase text-slate-500">
                {attentionHUD.visible ? 'CURRENT EVIDENCE' : 'EVIDENCE'}
              </div>
              <div>
                {(attentionHUD.visible ? attentionHUD.startTime : lastEvidenceWindow.startTime).toFixed(2)}s&ndash;{(attentionHUD.visible ? attentionHUD.endTime : lastEvidenceWindow.endTime).toFixed(2)}s
              </div>
              <div className="flex items-center gap-1.5 pt-1">
                {attentionHUD.visible ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse"></span>
                    <span className="text-rose-300 font-bold">ACTIVE NOW</span>
                  </>
                ) : (
                  <span className="text-slate-500">EVIDENCE WINDOW PASSED</span>
                )}
              </div>
            </div>
          )}

          {/* Metric Cards */}
          <div className="space-y-2 bg-[#11131A] p-3 rounded-sm border border-[#1E2232]">
            <div>
              <span className="text-[10px] text-slate-400 uppercase block">ANOMALY PROBABILITY</span>
              <span className="text-xl font-bold text-white">
                {activeJob.result.anomaly_probability != null
                  ? `${(activeJob.result.anomaly_probability * 100).toFixed(1)}%`
                  : 'N/A'}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-slate-400 uppercase block">LIKELY ACTION</span>
              <span className="text-xs font-bold text-blue-400 font-sans block">
                {activeJob.result.likely_action || 'None'}
              </span>
            </div>

            <div>
              <span className="text-[10px] text-slate-400 uppercase block">ACTION CONFIDENCE</span>
              <span className="text-xs font-bold text-emerald-400">
                {activeJob.result.action_confidence != null
                  ? `${(activeJob.result.action_confidence * 100).toFixed(1)}%`
                  : 'N/A'}
              </span>
            </div>
          </div>

          {/* INCIDENT RESPONSE PANEL -- the one and only tactical
              metrics table + dispatch workflow. (Previously there was a
              second, redundant "INCIDENT RESPONSE / DISPATCH READY" card
              right above this one repeating the same three numbers --
              removed; the metric cards above and this panel below are
              now the only two places these values render.) */}
          <div className="bg-[#11131A] p-3.5 rounded-sm border border-rose-500/40 space-y-3 font-mono">
            <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
              <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">INCIDENT RESPONSE</span>
              <span className="text-[9px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded-sm border border-rose-500/30 font-bold">DISPATCH READY</span>
            </div>

            {/* Status Banner */}
            <div className="p-2.5 bg-rose-950/40 border border-rose-500/40 rounded-sm flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse shrink-0"></span>
              <span className="text-xs font-bold text-rose-200 uppercase tracking-wide">
                🔴 ABNORMAL ACTIVITY DETECTED
              </span>
            </div>

            {/* Tactical Metrics Table */}
            <div className="space-y-1.5 text-[11px] font-mono">
              <div className="flex items-center justify-between py-1 border-b border-[#1A1D2A]">
                <span className="text-slate-400">Likely Action</span>
                <span className="font-bold text-white uppercase text-right max-w-[160px] truncate">
                  {activeJob.result.likely_action || 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-[#1A1D2A]">
                <span className="text-slate-400">Anomaly</span>
                <span className="font-bold text-rose-400">
                  {activeJob.result.anomaly_probability != null
                    ? `${(activeJob.result.anomaly_probability * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-[#1A1D2A]">
                <span className="text-slate-400">Action confidence</span>
                <span className="font-bold text-emerald-400">
                  {activeJob.result.action_confidence != null
                    ? `${(activeJob.result.action_confidence * 100).toFixed(1)}%`
                    : 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between py-1 border-b border-[#1A1D2A]">
                <span className="text-slate-400">Evidence</span>
                <span className="font-bold text-blue-400">
                  {(() => {
                    const start = activeJob.result?.evidence_window?.start ?? activeJob.result?.evidence_start_sec;
                    const end = activeJob.result?.evidence_window?.end ?? activeJob.result?.evidence_end_sec;
                    if (start != null && end != null) return `${start.toFixed(2)}s – ${end.toFixed(2)}s`;
                    if (activeJob.result?.temporal_anomaly_window) {
                      return `${activeJob.result.temporal_anomaly_window[0].toFixed(2)}s – ${activeJob.result.temporal_anomaly_window[1].toFixed(2)}s`;
                    }
                    return 'Full Stream Window';
                  })()}
                </span>
              </div>
            </div>

            {/* Incident Location */}
            <div className="space-y-1 pt-1">
              <span className="text-[10px] text-slate-400 uppercase block font-bold">INCIDENT LOCATION</span>
              <div className="p-2 bg-[#171A24] rounded-sm border border-[#232838] text-[11px] flex items-center gap-2">
                <Icons.MapPin className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span className="text-slate-200 truncate">
                  {activeJob.result?.location || activeJob.result?.camera_location || activeJob?.location || selectedSource?.location || 'LOCATION NOT CONFIGURED'}
                </span>
              </div>
            </div>

            {/* Location validation & Find Nearby Responders Button */}
            {!(selectedSource?.lat != null && selectedSource?.lng != null) && !(activeJob.result?.latitude != null && activeJob.result?.longitude != null) ? (
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-sm text-center space-y-1">
                <div className="text-amber-400 font-bold text-[11px] uppercase">INCIDENT LOCATION REQUIRED</div>
                <p className="text-slate-400 text-[10px] font-sans">
                  Attach GPS coordinates to camera feed or incident before searching for nearby officers.
                </p>
              </div>
            ) : (
              <button
                onClick={openDispatchModal}
                className="w-full py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-sm font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-md shadow-rose-600/20 uppercase tracking-wider"
              >
                <Icons.Radio className="w-3.5 h-3.5" />
                <span>FIND NEARBY RESPONDERS</span>
              </button>
            )}
          </div>

        </div>
      )}

      {/* STATE 4: COMPLETED YOLO RESULT PANEL */}
      {activeJob && activeJob.status === 'completed' && activeJob.system === 'vision_yolo' && activeJob.result && (
        <div className="space-y-4">

          {activeJob.result.object_summary && (
            <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
              <span className="text-[10px] text-slate-400 uppercase block font-bold">OBJECT SUMMARY</span>
              <div className="grid grid-cols-2 gap-2 text-center">
                <div className="bg-[#171A24] p-2 rounded-sm border border-[#232838]">
                  <div className="text-[10px] text-slate-400">PEOPLE</div>
                  <div className="text-lg font-bold text-blue-400">{activeJob.result.object_summary.people_count}</div>
                </div>
                <div className="bg-[#171A24] p-2 rounded-sm border border-[#232838]">
                  <div className="text-[10px] text-slate-400">VEHICLES</div>
                  <div className="text-lg font-bold text-indigo-400">{activeJob.result.object_summary.vehicles_count}</div>
                </div>
              </div>
            </div>
          )}

          {activeJob.result.detections && (
            <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
              <span className="text-[10px] text-slate-400 uppercase block font-bold">DETECTIONS ({activeJob.result.detections.length})</span>
              <div className="space-y-1 max-h-36 overflow-y-auto text-[11px]">
                {activeJob.result.detections.map((det, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-[#171A24] p-1.5 rounded-sm">
                    <span className="font-bold text-white uppercase">{det.class_name}</span>
                    <span className="text-blue-400">{(det.confidence * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeJob.result.tracks && (
            <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2">
              <span className="text-[10px] text-slate-400 uppercase block font-bold">ACTIVE TRACKS ({activeJob.result.tracks.length})</span>
              <div className="space-y-1.5 text-[10px]">
                {activeJob.result.tracks.map((trk, idx) => (
                  <div key={idx} className="p-1.5 bg-[#171A24] rounded-sm border border-[#232838] flex justify-between">
                    <span className="text-blue-400 font-bold">{trk.track_id} ({trk.class_name})</span>
                    <span className="text-slate-400">{trk.duration_sec}s &bull; {trk.direction}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      )}

      {/* STATE 5: FAILED ANALYSIS */}
      {activeJob && activeJob.status === 'failed' && (
        <div className="p-3.5 rounded-sm border bg-rose-500/10 border-rose-500/30 space-y-2">
          <div className="text-rose-400 font-bold text-xs flex items-center gap-2">
            <Icons.AlertTriangle className="w-4 h-4" />
            <span>ANALYSIS FAILED</span>
          </div>
          <p className="text-[11px] text-slate-300 font-mono whitespace-pre-wrap leading-relaxed">
            {activeJob.error || activeJob.result?.error || 'Inference error encountered on backend pipeline.'}
          </p>
        </div>
      )}

    </div>
  );
}
