import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { createApiClient } from './services/api';
import { haversineDistanceKm } from './lib/haversine';
import DashboardRightPanel from './components/dashboard-panel/DashboardRightPanel';
import { useIncidentAssistant } from './hooks/useIncidentAssistant';

/* ==========================================================================
   HIGH-TECH TACTICAL SVG ICONS (1:1 FIDELITY)
   ========================================================================== */
const Icon = ({ path, className = "w-4 h-4", viewBox = "0 0 24 24" }) => (
  <svg className={className} fill="none" viewBox={viewBox} stroke="currentColor" strokeWidth={1.75}>
    <path strokeLinecap="round" strokeLinejoin="round" d={path} />
  </svg>
);

const Icons = {
  Shield: (p) => <Icon path="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" {...p} />,
  Video: (p) => <Icon path="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" {...p} />,
  Activity: (p) => <Icon path="M22 12h-4l-3 9L9 3l-3 9H2" {...p} />,
  Upload: (p) => <Icon path="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" {...p} />,
  Terminal: (p) => <Icon path="M4 17l6-6-6-6M12 19h8" {...p} />,
  FileText: (p) => <Icon path="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zM14 2v6h6" {...p} />,
  Settings: (p) => <Icon path="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" {...p} />,
  CheckCircle: (p) => <Icon path="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" {...p} />,
  AlertTriangle: (p) => <Icon path="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01" {...p} />,
  Play: (p) => <Icon path="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" {...p} />,
  Cpu: (p) => <Icon path="M9 3v2m6-2v2M9 19v2m6-2v2M3 9h2m-2 6h2m14-6h2m-2 6h2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" {...p} />,
  Zap: (p) => <Icon path="M13 10V3L4 14h7v7l9-11h-7z" {...p} />,
  ChevronRight: (p) => <Icon path="M9 5l7 7-7 7" {...p} />,
  Server: (p) => <Icon path="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" {...p} />,
  Layers: (p) => <Icon path="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" {...p} />,
  X: (p) => <Icon path="M6 18L18 6M6 6l12 12" {...p} />,
  Crosshair: (p) => <Icon path="M12 2v4m0 12v4M2 12h4m12 0h4M12 8a4 4 0 100 8 4 4 0 000-8z" {...p} />,
  Bot: (p) => <Icon path="M12 2a2 2 0 012 2v2a2 2 0 01-2 2 2 2 0 01-2-2V4a2 2 0 012-2zm-7 7a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V9zm3 3h.01M16 12h.01M9 16h6" {...p} />,
  User: (p) => <Icon path="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" {...p} />,
  Send: (p) => <Icon path="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" {...p} />,
  Sparkles: (p) => <Icon path="M5 3v4M3 5h4M6 17v4m-2-2h4m11-16l1.2 3.6L20 10l-3.6 1.2L15 15l-1.2-3.6L10 10l3.6-1.2L15 4z" {...p} />,
  Paperclip: (p) => <Icon path="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" {...p} />,
  Copy: (p) => <Icon path="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" {...p} />,
  RefreshCw: (p) => <Icon path="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" {...p} />,
  CornerDownLeft: (p) => <Icon path="M9 10l-5 5m0 0l5 5m-5-5h11a4 4 0 004-4V4" {...p} />,
  Map: (p) => <Icon path="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" {...p} />,
  Radio: (p) => <Icon path="M4.929 4.929a10 10 0 0114.142 0M7.757 7.757a6 6 0 018.486 0M10.586 10.586a2 2 0 012.828 0M12 14v6" {...p} />,
  MapPin: (p) => <Icon path="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 11-6 0 3 3 0 016 0z" {...p} />,
  Plus: (p) => <Icon path="M12 4v16m8-8H4" {...p} />,
  Phone: (p) => <Icon path="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" {...p} />,
  Users: (p) => <Icon path="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" {...p} />,
  ExternalLink: (p) => <Icon path="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" {...p} />,
  Trash2: (p) => <Icon path="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" {...p} />,
  Smartphone: (p) => <Icon path="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" {...p} />,
  MessageSquare: (p) => <Icon path="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" {...p} />
};

// Exported so new, out-of-file components (e.g.
// components/incident-assistant/AnalysisResultsPanel.jsx) can reuse the
// exact same icon set rather than duplicating it -- purely additive, no
// change to any existing usage of Icons within this file.
export { Icons };

/* ==========================================================================
   DEFAULT FEEDS & RESPONDERS (PINNED TO NIPANI CITY, KARNATAKA, INDIA)
   ========================================================================== */
const DEMO_VIDEO_SOURCES = [
  {
    id: 'FEED-NIPANI-NORTH-01',
    title: 'Perimeter Fence - Nipani Industrial Zone',
    type: 'anomaly',
    location: 'Zone A - Industrial Perimeter, Nipani, Karnataka, India',
    resolution: '1920x1080 @ 30 FPS',
    status: 'Active Feed',
    sampleName: 'perimeter_intrusion.mp4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
    lat: 16.4022,
    lng: 74.3820
  },
  {
    id: 'FEED-NIPANI-HIGHWAY-02',
    title: 'Nipani PB Road Highway Corridor',
    type: 'vision_yolo',
    location: 'NH48 Junction, Nipani, Belagavi Dist., Karnataka',
    resolution: '3840x2160 @ 60 FPS',
    status: 'Active Feed',
    sampleName: 'concourse_crowd.mp4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4',
    lat: 16.4085,
    lng: 74.3860
  },
  {
    id: 'FEED-NIPANI-CENTRAL-03',
    title: 'Nipani Municipal Facility & Depot',
    type: 'anomaly',
    location: 'Central Town Sector, Nipani, Karnataka, India',
    resolution: '1920x1080 @ 60 FPS',
    status: 'Active Feed',
    sampleName: 'vault_breach_test.mp4',
    videoUrl: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerFun.mp4',
    lat: 16.3980,
    lng: 74.3795
  }
];


const TACTICAL_RESPONDERS = [
  {
    id: 'PATROL-NIPANI-01',
    unit: 'Nipani Highway Patrol Alpha',
    location: 'NH-48 Highway Junction, Nipani',
    lat: 16.4045,
    lng: 74.3840,
    status: 'Active Patrol',
    eta: '1.2 min'
  },
  {
    id: 'SECTOR-NIPANI-02',
    unit: 'Nipani KSRTC Sector Squad',
    location: 'Bus Terminal Sector, Central Nipani',
    lat: 16.4010,
    lng: 74.3815,
    status: 'Stationary',
    eta: '2.5 min'
  },
  {
    id: 'INTERCEPT-NIPANI-03',
    unit: 'Belagavi District Special Recon',
    location: 'Industrial Estate Road, Nipani',
    lat: 16.3965,
    lng: 74.3770,
    status: 'En Route',
    eta: '3.8 min'
  }
];


// CartoDB Voyager Tile API URL with User-supplied API key
const CARTO_VOYAGER_TILE_URL = "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_4ckp_1_7534d1fa2c9926ff66187e39";

/* ==========================================================================
   TEMPORAL MODEL EVIDENCE TIMELINE COMPONENT
   ========================================================================== */
function formatTacticalTime(seconds) {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return '--:--.-';
  const mm = Math.floor(seconds / 60);
  const ss = (seconds % 60).toFixed(1).padStart(4, '0');
  return `${String(mm).padStart(2, '0')}:${ss}`;
}

// Evenly-spaced dynamic time-scale tick marks for the single-track timeline.
// Picks a "nice" step (5/10/15/30/60s family) so there are roughly 4-7 ticks
// regardless of real video duration -- never hardcoded timestamps.
function pickTickStep(durationSeconds) {
  const target = durationSeconds / 5;
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
  return steps.find((s) => s >= target) || steps[steps.length - 1];
}

/* ==========================================================================
   STEP 2E (v5): VIDEO ACTIVITY TIMELINE -- three-state reached/clear/
   abnormal/unreached track. The shell (track + time scale + playhead)
   depends ONLY on a valid video.duration -- it renders before the backend
   result exists and is never gated on activeJob/analysis state. Analysis
   data only ever adds color on top of that always-present shell:
     - GREEN "reached, no anomaly": real genuinely-played coverage only,
       from the caller's `reachedRanges` (computed by App from timeupdate +
       seek classification -- see reachedRanges' comment in App). A SEEK is
       NOT playback: the gap a forward seek skips over carries no range at
       all, so it is NEVER painted green -- it falls through to DARK
       instead. This is what distinguishes "actually observed, no anomaly"
       from "simply hasn't been checked".
     - RED "reached, abnormal": real detected intervals, clipped to
       `visibleRegions` (computed by the caller every render from
       currentTime + segmentStart -- see segmentStart's comment in App).
       This is intentionally NOT a permanent visual history: a region only
       stays red for as long as currentTime continues to actually justify
       it. Seeking backward past a region's end immediately drops it;
       resuming playback regrows it progressively from wherever the
       current uninterrupted segment actually started observing.
     - DARK "not yet reached / skipped by a seek / unknown": everything not
       covered by a green or red segment above (the base layer).
   No fabricated frame-level predictions -- green only ever means "this
   portion of the video has actually been played through without a
   qualifying anomaly event under the existing temporal evidence logic",
   never an independent per-frame classification, and never a claim about
   time a seek merely skipped over. No Stage 2 row, no per-window bar graph.
   ========================================================================== */
function TemporalEvidenceTimeline({ currentTime, duration, videoRef, visibleRegions, reachedRanges, evidenceEndTime, isAnomaly }) {
  // Shell existence depends ONLY on a valid video duration -- never on
  // activeJob/analysis result. Nothing to render yet if the video hasn't
  // reported a duration.
  if (!duration || !Number.isFinite(duration) || duration <= 0) return null;

  const effectiveDuration = duration;
  const safeCurrentTime = Math.min(Math.max(currentTime || 0, 0), effectiveDuration);
  const playheadPct = (safeCurrentTime / effectiveDuration) * 100;
  // STEP 2E (v6): GREEN "reached, no anomaly" layer -- rendered from the
  // caller's reachedRanges (genuine playback coverage only), NOT from a
  // naive [0, currentTime] span. A forward seek is not playback: the
  // skipped gap carries no range at all, so it correctly falls through to
  // the DARK base layer instead of being falsely painted green. Each range
  // is clamped into [0, effectiveDuration] AND into [0, evidenceEndTime] --
  // the backend only ever analyzes a prefix of the video (fixed-size
  // sliding windows from t=0), so playback past the last window it actually
  // produced evidence for was never judged "clean" by the model. That
  // trailing played-but-unjudged stretch must not render as GREEN; it's
  // carved out here and picked up by amberSegments below instead.
  // evidenceEndTime === null means there's no evidence at all for this job
  // (e.g. a normal-video result) -- treated as "no coverage limit", so
  // green still renders its full genuinely-played extent in that case.
  const hasEvidenceLimit = evidenceEndTime !== null && evidenceEndTime !== undefined;
  const greenSegments = (reachedRanges || [])
    .map(r => ({
      start: Math.max(0, r.start),
      end: Math.min(effectiveDuration, hasEvidenceLimit ? Math.min(r.end, evidenceEndTime) : r.end),
    }))
    .filter(r => r.end > r.start);
  // STEP 2E (v6): AMBER "played, but never evaluated by the model" layer --
  // the part of reachedRanges that falls beyond evidenceEndTime. This is
  // genuinely different from the DARK "not yet reached" base layer: the
  // viewer DID watch this footage, the model just never produced temporal
  // evidence for it, so it must not be silently claimed as either "clean"
  // (green) or "unplayed" (dark).
  const amberSegments = hasEvidenceLimit
    ? (reachedRanges || [])
        .map(r => ({ start: Math.max(evidenceEndTime, r.start), end: Math.min(effectiveDuration, r.end) }))
        .filter(r => r.end > r.start)
    : [];
  // visibleRegions already carries only the currently-justified red extent
  // of each real detected interval (see the doc comment above). isAnomaly is
  // the same whole-video anomaly_detected gate already used elsewhere -- a
  // normal-video job never has non-empty visibleRegions anyway, this is
  // just defense in depth against stale state.
  const regions = isAnomaly ? (visibleRegions || []) : [];

  const seekTo = (seconds) => {
    const video = videoRef?.current;
    if (!video) return;
    video.currentTime = seconds;
  };

  const tickStep = pickTickStep(effectiveDuration);
  const ticks = [];
  for (let t = 0; t <= effectiveDuration + 0.001; t += tickStep) ticks.push(t);
  if (ticks[ticks.length - 1] < effectiveDuration - tickStep * 0.4) ticks.push(effectiveDuration);

  return (
    <div className="mt-3 p-3 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-1.5 font-mono text-xs">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-white font-bold text-[11px]">
          <Icons.Zap className="w-3.5 h-3.5 text-blue-400" />
          <span>VIDEO ACTIVITY</span>
        </div>
        <span className="text-slate-200 tabular-nums text-[10px]">
          {formatTacticalTime(currentTime)} / {formatTacticalTime(duration)}
        </span>
      </div>

      {/* Dynamic time scale, calculated from the real video duration */}
      <div className="relative h-3 text-[9px] text-slate-500">
        {ticks.map((t, idx) => (
          <span
            key={idx}
            className="absolute -translate-x-1/2 tabular-nums"
            style={{ left: `${Math.min(100, Math.max(0, (t / effectiveDuration) * 100))}%` }}
          >
            {formatTacticalTime(t)}
          </span>
        ))}
      </div>

      {/* ALWAYS-VISIBLE timeline track -- exists purely from video.duration */}
      <div className="relative h-7 bg-[#08090C] border border-[#1E2232] rounded-sm overflow-hidden">
        {/* DARK base layer = not yet reached / skipped-by-seek / unknown
            (the default, full width -- anything not covered by a green or
            red segment below simply shows this). */}
        {/* GREEN reached layer -- one segment per genuinely-played
            reachedRanges entry. A forward seek closes off the range it
            interrupts and starts a new one at the landing point, so the
            skipped gap has NO segment here and correctly shows DARK instead
            of being falsely claimed as "observed, no anomaly". */}
        {greenSegments.map((r, idx) => {
          const left = (r.start / effectiveDuration) * 100;
          const width = ((r.end - r.start) / effectiveDuration) * 100;
          return (
            <div
              key={idx}
              className="absolute inset-y-0 bg-emerald-600/80"
              style={{ left: `${left}%`, width: `${width}%` }}
            />
          );
        })}
        {/* AMBER "played, but never evaluated by the model" layer -- the
            model only ever analyzes a prefix of the video (fixed-size
            sliding windows from t=0), so playback past evidenceEndTime was
            genuinely watched but never judged clean. Rendered separately
            from GREEN so that absence of evidence is never shown as
            evidence of absence. */}
        {amberSegments.map((r, idx) => {
          const left = (r.start / effectiveDuration) * 100;
          const width = ((r.end - r.start) / effectiveDuration) * 100;
          return (
            <div
              key={idx}
              className="absolute inset-y-0 bg-amber-500/70"
              style={{ left: `${left}%`, width: `${width}%` }}
              title="Played, but beyond the model's analyzed window range"
            />
          );
        })}
        {/* RED visible anomaly regions. `r.start`/`r.end` here are already
            the currently-justified visible extent (clipped by the caller's
            visibleAnomalyRegions = max(interval.start, segmentStart) ..
            min(currentTime, interval.end)) -- rendered as-is, with no
            further clamping against currentTime. A region simply isn't in
            `regions` at all once it's no longer justified (e.g. a backward
            seek moved past its end), so it disappears on the very next
            render instead of staying as permanent history. */}
        {regions.map((r, idx) => {
          const left = (r.start / effectiveDuration) * 100;
          const width = Math.max(0.4, ((r.end - r.start) / effectiveDuration) * 100);
          return (
            <button
              key={idx}
              type="button"
              onClick={() => seekTo(r.start)}
              className="absolute inset-y-0 bg-rose-600 hover:bg-rose-500 cursor-pointer transition-colors z-10"
              style={{ left: `${left}%`, width: `${width}%` }}
              aria-label={`Seek to model evidence window at ${r.start.toFixed(1)} seconds`}
              title={`ABNORMAL MODEL EVIDENCE WINDOW ${r.start.toFixed(1)}s - ${r.end.toFixed(1)}s (window-level evidence, not a frame-accurate onset)`}
            />
          );
        })}

        {/* Synchronized playhead -- driven solely by the real HTMLVideoElement.currentTime, no second timer */}
        <div className="absolute top-0 bottom-0 w-[2px] bg-white z-20 pointer-events-none" style={{ left: `${playheadPct}%` }} />
      </div>

      {/* Compact legend */}
      <div className="flex items-center gap-3 text-[9px] text-slate-400 font-sans flex-wrap">
        <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 bg-emerald-600/80 rounded-[1px]" /> NO ANOMALY</span>
        <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 bg-rose-600 rounded-[1px]" /> ABNORMAL MODEL EVIDENCE</span>
        <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 bg-amber-500/70 rounded-[1px]" /> PLAYED, NOT EVALUATED</span>
        <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 bg-[#1E2232] rounded-[1px]" /> NOT YET REACHED</span>
      </div>
    </div>
  );
}

/* ==========================================================================
   MAIN SENTINEL APPLICATION CONTROLLER
   ========================================================================== */
export default function App() {
  const [view, setView] = useState('landing'); // 'landing' | 'analysis' | 'copilot' | 'tracker' | 'logs' | 'settings'
  const [previousView, setPreviousView] = useState('landing');
  const [settingsTab, setSettingsTab] = useState('overview'); // 'overview' | 'backend' | 'sms' | 'responders' | 'interface' | 'diagnostics'
  const [analysisMode, setAnalysisMode] = useState('anomaly'); // 'anomaly' | 'vision_yolo'
  // Prefer the build-time VITE_API_BASE_URL (frontend/.env) over a
  // hardcoded localhost default -- "localhost" only resolves to the
  // backend when this page is loaded on the same machine as the backend.
  // On any other device (e.g. an officer's phone opening a duty link
  // served over a public tunnel), "localhost" means that device, so the
  // app would silently fail every API call without this.
  const [backendUrl, setBackendUrl] = useState(
    import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  );
  const [apiHealth, setApiHealth] = useState({ connected: false, checking: true, details: null, error: null, latencyMs: null });
  const [showMapModal, setShowMapModal] = useState(false);
  const [simulatedEngineMode, setSimulatedEngineMode] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [yoloHealth, setYoloHealth] = useState({ status: 'checking', yolo_ready: false });
  const [smsGatewayStatus, setSmsGatewayStatus] = useState(null);
  const [diagnosticLog, setDiagnosticLog] = useState(null);
  const [isRunningDiagnostics, setIsRunningDiagnostics] = useState(false);

  // SMS Gateway (Communications settings) -- config dashboard for the
  // Android "SMS Gateway" Local Server integration. smsPasswordInput is
  // kept separate from smsConfig and never persisted/sent unless non-empty,
  // so the real saved password is never displayed back in the UI.
  const [smsConfig, setSmsConfig] = useState({ enabled: false, url: '', username: '', password_configured: false });
  const [smsPasswordInput, setSmsPasswordInput] = useState('');
  const [smsConfigLoaded, setSmsConfigLoaded] = useState(false);
  const [smsConfigSaving, setSmsConfigSaving] = useState(false);
  const [smsConnectionState, setSmsConnectionState] = useState('idle'); // idle | testing | connected | unreachable | auth-failed | invalid-config
  const [smsConnectionDetail, setSmsConnectionDetail] = useState(null);
  const [smsLastCheckedAt, setSmsLastCheckedAt] = useState(null);
  const [smsTestRecipient, setSmsTestRecipient] = useState('');
  const [smsTestSmsState, setSmsTestSmsState] = useState('idle'); // idle | sending | sent | failed
  const [smsTestSmsDetail, setSmsTestSmsDetail] = useState(null);

  // --- Incident Response & Nearby Responder Dispatch State ---------
  const [showDispatchModal, setShowDispatchModal] = useState(false);
  const [nearbyResponders, setNearbyResponders] = useState([]);
  const [isLoadingNearby, setIsLoadingNearby] = useState(false);
  const [selectedResponderForDispatch, setSelectedResponderForDispatch] = useState(null);
  const [dispatchPreviewMessage, setDispatchPreviewMessage] = useState('');
  const [isSendingDispatch, setIsSendingDispatch] = useState(false);
  const [dispatchOutcome, setDispatchOutcome] = useState(null);

  // --- Responder Registry & Field Personnel State -----------------
  const [registeredResponders, setRegisteredResponders] = useState([]);
  const [isLoadingResponders, setIsLoadingResponders] = useState(false);
  const [newResponderForm, setNewResponderForm] = useState({ name: '', unit: '', role: '', phone: '' });
  const [isRegisteringResponder, setIsRegisteringResponder] = useState(false);

  // Field Personnel Workspace State
  const [showAddOfficerModal, setShowAddOfficerModal] = useState(false);
  const [addOfficerForm, setAddOfficerForm] = useState({ name: '', id: '', phone_number: '', role: 'Police Officer', unit: '', username: '', password: '' });
  const [addOfficerError, setAddOfficerError] = useState(null);
  const [isSubmittingOfficer, setIsSubmittingOfficer] = useState(false);
  // Shown once immediately after a successful create -- the raw password is
  // never recoverable after this, same discipline as the PIN. Cleared when
  // the operator closes this confirmation or opens Add Officer again.
  const [createdOfficerCredentials, setCreatedOfficerCredentials] = useState(null);
  const [sendDutyLinkModalOfficer, setSendDutyLinkModalOfficer] = useState(null);
  const [isSendingDutyLink, setIsSendingDutyLink] = useState(false);
  const [dutyLinkOutcome, setDutyLinkOutcome] = useState(null);
  const [personnelFilter, setPersonnelFilter] = useState('ALL'); // 'ALL' | 'LIVE' | 'ON_DUTY' | 'OFF_DUTY'
  const [personnelSearch, setPersonnelSearch] = useState('');
  const [personnelDeletingId, setPersonnelDeletingId] = useState(null);

  // Mobile Responder Duty Page State (/responder/duty/:token)
  // `dutyToken` here is the URL path id (the officer-identifying link an
  // operator sends) -- NOT the signed share-session token. The signed
  // token used for authenticated /v1/share/{token}/* calls lives in
  // `dutySessionToken`, obtained only via a real username/password login.
  const [dutyToken, setDutyToken] = useState('');
  const [dutyOfficer, setDutyOfficer] = useState(null);
  const [dutyLoading, setDutyLoading] = useState(false);
  const [dutyError, setDutyError] = useState(null);
  const [dutyIsActive, setDutyIsActive] = useState(false);
  // Login state -- gates the duty UI. "Stay logged in" is persisted in
  // localStorage per-officer-id so reopening the same link later skips the
  // login form (per the operator's explicit preference), cleared on
  // explicit "STOP DUTY".
  const [dutySessionToken, setDutySessionToken] = useState(null);
  const [dutyLoginForm, setDutyLoginForm] = useState({ username: '', password: '' });
  const [dutyLoginError, setDutyLoginError] = useState(null);
  const [dutyLoginSubmitting, setDutyLoginSubmitting] = useState(false);
  const [dutyLocationStatus, setDutyLocationStatus] = useState('not_sharing'); // 'not_sharing' | 'live' | 'waiting' | 'permission_denied' | 'unavailable' | 'error'
  const [dutyGpsData, setDutyGpsData] = useState({ latitude: null, longitude: null, accuracy_meters: null, last_seen_at: null });
  const [dutyGpsErrorDetail, setDutyGpsErrorDetail] = useState(null);
  const [dutySecondsSinceUpdate, setDutySecondsSinceUpdate] = useState(0);
  const dutyWatchIdRef = useRef(null);
  const [dutyAssistantMessages, setDutyAssistantMessages] = useState([
    { sender: 'assistant', text: 'SENTINEL-X Field Assistant ready. Tap a quick question below or ask about your duty status and live GPS telemetry.' }
  ]);
  const [dutyAssistantInput, setDutyAssistantInput] = useState('');

  // Live GPS Tracker for field devices (standalone test view)
  // LIVE GPS tab: read-only dispatcher map of real on-duty responder
  // locations (pulled from registeredResponders, same data the officer's
  // own phone writes via the duty-session flow). Replaces the old
  // "broadcast as any responder" tool -- that let anyone with the dashboard
  // open spoof any responder's location with no auth check on the backend
  // write endpoint. This view only reads, it never writes a location.
  const [selectedTrackerResponderId, setSelectedTrackerResponderId] = useState('');
  const [trackerAutoRefresh, setTrackerAutoRefresh] = useState(true);
  const trackerMapContainerRef = useRef(null);
  const trackerMapInstanceRef = useRef(null);
  const trackerMarkersRef = useRef([]);
  // Incident the selected responder was last dispatched to (looked up from
  // the audit log's "dispatch_sent" entries -- there is no separate
  // persistent assignment record, see send_dispatch's docstring point 3 on
  // the backend). Null when the responder has no recent successful
  // dispatch on record.
  const [trackerAssignedIncident, setTrackerAssignedIncident] = useState(null);
  const [trackerRouteLoading, setTrackerRouteLoading] = useState(false);
  const [trackerRouteError, setTrackerRouteError] = useState(null);
  const trackerRouteLayerRef = useRef(null);

  // Selected video feed / custom upload
  const [selectedSource, setSelectedSource] = useState(DEMO_VIDEO_SOURCES[0]);
  const [customFile, setCustomFile] = useState(null);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState(DEMO_VIDEO_SOURCES[0].videoUrl);

  // Incident location settings (custom uploads only -- demo camera sources
  // keep their own fixed real-world lat/lng and the GEOLOCATE map viewer).
  // Default is the operator's own pinned location (Nipani Bus Stand) until
  // changed via the settings modal; persists across uploads for the
  // session so it doesn't need to be re-set for every video.
  const DEFAULT_INCIDENT_LOCATION = {
    lat: 16.4044521,
    lng: 74.3790313,
    label: 'Nipani Bus Stand, Karnataka, India',
  };
  const [incidentLocation, setIncidentLocation] = useState(DEFAULT_INCIDENT_LOCATION);
  const [showIncidentLocationModal, setShowIncidentLocationModal] = useState(false);
  const [incidentLocationLinkInput, setIncidentLocationLinkInput] = useState('');
  const [incidentLocationResolving, setIncidentLocationResolving] = useState(false);
  const [incidentLocationError, setIncidentLocationError] = useState(null);

  // Video playback time tracking for temporal timeline
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(null);

  // Step 2B: Real-time temporal attention HUD state. Driven by onTimeUpdate
  // against the whole-video result's temporal_evidence windows -- the HUD
  // only ever displays the whole-video likely_action / action_confidence
  // (never a per-window classification), and visibility is purely a function
  // of whether the current playback position falls inside a high-attention
  // window.
  const [attentionHUD, setAttentionHUD] = useState({ visible: false });

  /* STEP 2D: once the first real qualifying evidence window is reached for
     THIS analysis job, the Intelligence Panel latches into INCIDENT
     DETECTED permanently -- it must never fall back to ANALYSIS READY just
     because currentTime later leaves the window. attentionHUD itself (the
     Step 2B/2C currentTime-driven HUD) is untouched and keeps appearing/
     disappearing as before. encounteredJobIdRef tracks which job the latch
     belongs to, so a brand new analysis (new jobId) starts fresh. */
  const [hasEncounteredEvidence, setHasEncounteredEvidence] = useState(false);
  const encounteredJobIdRef = useRef(null);
  // STEP 2D: the most recent qualifying window actually encountered, kept
  // around after currentTime leaves it so "EVIDENCE WINDOW PASSED" can still
  // show which real window was found -- never cleared, only overwritten by
  // a newer qualifying window of the SAME job.
  const [lastEvidenceWindow, setLastEvidenceWindow] = useState(null);

  // STEP 2E (v4): the single-track timeline has NO permanent memory of its
  // own. Red reveal is recomputed on every render purely from the current
  // playback position + the current "segment start" (see segmentStart below)
  // -- never accumulated/latched. This is intentionally a DIFFERENT concept
  // from Step 2D's hasEncounteredEvidence/lastEvidenceWindow incident latch
  // above, which stays untouched and keeps its own permanent semantics for
  // the Intelligence Panel.
  //
  // segmentStart = the earliest point the CURRENT uninterrupted playback
  // segment can honestly claim to have observed. It is the left-bound used
  // together with currentTime to decide how much of each anomaly interval is
  // allowed to render as red:
  //   visibleStart = max(interval.start, segmentStart)
  //   visibleEnd   = min(currentTime, interval.end)
  //   visible iff  visibleEnd > visibleStart
  // Update rules (see handleSeeking/handleSeeked/handleTimeUpdate below):
  //   - genuine continuous playback (timeupdate, no seek in between): leave
  //     segmentStart untouched -- intervals already "entered" keep growing.
  //   - a BACKWARD seek (new time < last known time): reset segmentStart to
  //     0. Rewinding can only ever remove false claims (currentTime itself
  //     already hides anything ahead of the new position) -- it never fakes
  //     new ones, so it's always safe to treat it like a fresh pass from 0.
  //   - a FORWARD seek (new time > last known time): set segmentStart to the
  //     seek destination. The skipped gap must never be claimed as observed,
  //     so nothing before the landing point can count toward any interval.
  //   - a brand new analysis job: reset to 0, same reset point Step 2D uses.
  const [segmentStart, setSegmentStart] = useState(0);
  // STEP 2E (v5): GENUINELY reached playback coverage, as a list of merged
  // [start, end] ranges -- this is what the timeline's GREEN layer renders
  // from now, replacing the old naive [0, currentTime] assumption. A forward
  // SEEK is not playback: the skipped gap must never be painted green (that
  // would falsely claim the AI/the viewer observed it), so it must stay in
  // the DARK "not yet reached" state instead. Update rules:
  //   - genuine continuous playback (timeupdate, not mid-seek): extend the
  //     LAST range's end to the new currentTime (creating the first range if
  //     none exists yet).
  //   - a BACKWARD seek: ranges are left untouched. They are honest history
  //     of what was actually played and backward seeking never un-plays
  //     anything; the playhead moving back already visually caps how far
  //     green can currently extend (see rendering below), and resuming
  //     forward playback simply continues extending the existing range it
  //     lands back inside of -- no new gap is introduced.
  //   - a FORWARD seek: close off by pushing a brand new zero-width range
  //     starting at the destination. This leaves the skipped gap covered by
  //     NO range at all, so it renders dark/unknown instead of green.
  //   - a brand new analysis job: reset to a single zero-width range at 0,
  //     same reset point segmentStart uses.
  const [reachedRanges, setReachedRanges] = useState([{ start: 0, end: 0 }]);
  // Last known real playback position, used only to classify the next seek
  // as forward or backward. Updated on every timeupdate AND on every seeked.
  const lastKnownTimeRef = useRef(0);
  // True strictly between the native `seeking` and `seeked` events, so a
  // stray timeupdate firing mid-seek can't be misread as genuine playback.
  const isSeekingRef = useRef(false);

  // Video Bounding Box Toggles for YOLO mode
  const [toggleDetections, setToggleDetections] = useState(true);
  const [toggleTracks, setToggleTracks] = useState(true);

  // Active Job State
  const [activeJob, setActiveJob] = useState(null);

  // True from the moment a video source is selected/uploaded until the
  // backend job actually leaves 'queued' (i.e. starts real processing).
  // Playback is intentionally held back during this window -- see the
  // "AUTOMATIC ANALYSIS TRIGGER" section below for why: starting playback
  // immediately (the old autoPlay behavior) let the video's own clock race
  // ahead of a job that was often still uploading/queued, which is what
  // made the timeline look wrong (all green, then a late result flips
  // segments red after the fact) on anything but a very fast connection.
  // CHANGE LOG (added this session, revert by removing this flag, the
  // loading-overlay JSX gated on it, and restoring `autoPlay` on the main
  // <video> element + moving submitActiveJob's call back into
  // handleVideoPlay if this causes problems):
  const [isAwaitingBackendStart, setIsAwaitingBackendStart] = useState(false);

  // Per-source analysis guard ref: ensures ONLY ONE analysis job is triggered per video source
  const currentAnalyzedSourceKeyRef = useRef(null);

  // Historical Audit Logs
  const [jobHistory, setJobHistory] = useState([]);

  // Session Events (audit log) detail modal -- which entry is expanded.
  const [selectedAuditEntry, setSelectedAuditEntry] = useState(null);

  // job_id -> { videoUrl, lat, lng, locationLabel } captured at the moment
  // each analysis job is submitted. This is the ONLY place a job's source
  // video is ever recoverable from later (the backend never persists the
  // uploaded video itself -- see AnalysisResult schema), so the audit-log
  // detail view can only show a clip for a job still in this lookup, i.e.
  // one submitted during the current browser session. A ref (not state)
  // since nothing needs to re-render when this map is written to -- it's
  // read only on-demand when an audit entry is expanded.
  const jobSourceInfoRef = useRef({});

  // Selected Tactical Responder
  const [selectedResponder, setSelectedResponder] = useState(TACTICAL_RESPONDERS[0]);

  // Canvas ref for overlay bounding box drawing
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  // Leaflet Map Refs
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const tileLayerRef = useRef(null);
  const markersRef = useRef([]);
  const mapResizeObserverRef = useRef(null);

  const apiClient = useMemo(() => createApiClient(backendUrl), [backendUrl]);

  const showToast = useCallback((msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  }, []);

  // AI Incident Assistant tab: latest-incident summary + eligible-
  // responder forwarding, entirely real-backend-data-driven (see
  // hooks/useIncidentAssistant.js).
  const incidentAssistant = useIncidentAssistant(apiClient);

  // Navigation controls for full-page Settings workspace
  const openSettings = useCallback((tab = 'overview') => {
    if (view !== 'settings') {
      setPreviousView(view);
    }
    setSettingsTab(tab);
    setView('settings');
  }, [view]);

  const closeSettings = useCallback(() => {
    setView(previousView || 'landing');
  }, [previousView]);

  // Backend Health Poller
  const checkBackendHealth = useCallback(async () => {
    setApiHealth(prev => ({ ...prev, checking: true }));
    const t0 = performance.now();
    const health = await apiClient.checkHealth();
    const dt = Math.round(performance.now() - t0);
    setApiHealth({
      connected: health.connected,
      checking: false,
      details: health.data || null,
      error: health.error || null,
      latencyMs: dt
    });
  }, [apiClient]);

  useEffect(() => {
    checkBackendHealth();
    const timer = setInterval(checkBackendHealth, 10000);
    return () => clearInterval(timer);
  }, [checkBackendHealth]);

  // --- SMS Gateway (Communications settings) ---------------------------
  // Status badge color helpers, same 3-color idiom used elsewhere in this
  // app (emerald=connected/good, rose=hard failure, amber=warning/not-yet-
  // attempted, blue=in-progress, slate=idle/no attempt made).
  const smsBadgeClassFor = (state) => ({
    connected: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    unreachable: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
    'auth-failed': 'bg-rose-500/10 border-rose-500/30 text-rose-400',
    'invalid-config': 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    testing: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    idle: 'bg-slate-500/10 border-slate-500/30 text-slate-400',
  }[state] || 'bg-slate-500/10 border-slate-500/30 text-slate-400');

  const smsDotClassFor = (state) => ({
    connected: 'bg-emerald-400 animate-pulse',
    unreachable: 'bg-rose-400',
    'auth-failed': 'bg-rose-400',
    'invalid-config': 'bg-amber-400',
    testing: 'bg-blue-400 animate-pulse',
    idle: 'bg-slate-400',
  }[state] || 'bg-slate-400');

  const smsLabelFor = (state) => ({
    connected: 'CONNECTED',
    unreachable: 'UNREACHABLE',
    'auth-failed': 'AUTH FAILED',
    'invalid-config': 'NOT CONFIGURED',
    testing: 'TESTING...',
    idle: 'NOT CHECKED',
  }[state] || 'NOT CHECKED');

  const fetchSmsConfig = useCallback(async () => {
    try {
      const cfg = await apiClient.getSmsConfig();
      setSmsConfig(cfg);
      setSmsConfigLoaded(true);
    } catch (err) {
      showToast(`Failed to load SMS gateway config: ${err.message}`);
    }
  }, [apiClient, showToast]);

  const fetchSmsStatus = useCallback(async () => {
    try {
      const status = await apiClient.getSmsStatus();
      setSmsGatewayStatus(status);
      if (!status.configured) {
        setSmsConnectionState('invalid-config');
      } else if (status.connected === true) {
        setSmsConnectionState('connected');
      } else if (status.connected === false) {
        setSmsConnectionState('unreachable');
      } else {
        setSmsConnectionState('idle');
      }
    } catch {
      // ignore
    }
  }, [apiClient]);

  const fetchYoloHealth = useCallback(async () => {
    try {
      const yolo = await apiClient.getYoloHealth();
      setYoloHealth(yolo);
    } catch (err) {
      setYoloHealth({ status: 'offline', error: err.message, yolo_ready: false });
    }
  }, [apiClient]);

  const runFullDiagnostics = useCallback(async () => {
    setIsRunningDiagnostics(true);
    const results = {
      timestamp: new Date().toISOString(),
      backendUrl,
      health: null,
      yolo: null,
      sms: null,
      clientSession: {
        currentView: view,
        previousView,
        activeSource: selectedSource.id,
        analysisMode,
        historyCount: jobHistory.length
      }
    };
    try {
      results.health = await apiClient.checkHealth();
    } catch (e) {
      results.health = { error: e.message };
    }
    try {
      results.yolo = await apiClient.getYoloHealth();
    } catch (e) {
      results.yolo = { error: e.message };
    }
    try {
      results.sms = await apiClient.getSmsStatus();
    } catch (e) {
      results.sms = { error: e.message };
    }
    setDiagnosticLog(results);
    setIsRunningDiagnostics(false);
    showToast('System diagnostics complete.');
  }, [apiClient, backendUrl, view, previousView, selectedSource.id, analysisMode, jobHistory.length, showToast]);

  // Fetch current backend settings when Settings view opens
  useEffect(() => {
    if (view === 'settings') {
      checkBackendHealth();
      fetchSmsConfig();
      fetchSmsStatus();
      fetchYoloHealth();
    } else {
      setSmsPasswordInput('');
    }
  }, [view, checkBackendHealth, fetchSmsConfig, fetchSmsStatus, fetchYoloHealth]);

  const classifySmsError = (errorText) => {
    const text = (errorText || '').toLowerCase();
    if (text.includes('not configured') || text.includes('disabled')) return 'invalid-config';
    if (text.includes('401') || text.includes('403') || text.includes('auth')) return 'auth-failed';
    return 'unreachable';
  };

  const handleSaveSmsConfig = useCallback(async () => {
    setSmsConfigSaving(true);
    try {
      const updated = await apiClient.updateSmsConfig({
        enabled: smsConfig.enabled,
        url: smsConfig.url,
        username: smsConfig.username,
        password: smsPasswordInput || null,
      });
      setSmsConfig(updated);
      setSmsPasswordInput('');
      await fetchSmsStatus();
      showToast('SMS gateway configuration saved successfully.');
    } catch (err) {
      showToast(`Failed to save SMS gateway config: ${err.message}`);
    } finally {
      setSmsConfigSaving(false);
    }
  }, [apiClient, smsConfig, smsPasswordInput, fetchSmsStatus, showToast]);

  const handleTestSmsConnection = useCallback(async () => {
    setSmsConnectionState('testing');
    setSmsConnectionDetail(null);
    try {
      const result = await apiClient.testSmsConnection();
      if (result.success) {
        setSmsConnectionState('connected');
        setSmsConnectionDetail(result.message || 'Connection established successfully.');
        showToast('SMS Gateway connection verified.');
      } else {
        setSmsConnectionState(classifySmsError(result.error));
        setSmsConnectionDetail(result.error || result.message || 'Connection test failed.');
      }
    } catch (err) {
      setSmsConnectionState('unreachable');
      setSmsConnectionDetail(err.message);
    } finally {
      setSmsLastCheckedAt(new Date());
      await fetchSmsStatus();
    }
  }, [apiClient, fetchSmsStatus, showToast]);

  const handleSendTestSms = useCallback(async () => {
    setSmsTestSmsState('sending');
    try {
      const result = await apiClient.sendTestSms(smsTestRecipient.trim());
      if (result.success) {
        setSmsTestSmsState('sent');
        setSmsTestSmsDetail(result.message || null);
        showToast('Test SMS sent successfully.');
      } else {
        setSmsTestSmsState('failed');
        setSmsTestSmsDetail(result.error || result.message || 'Test SMS rejected.');
      }
    } catch (err) {
      setSmsTestSmsState('failed');
      setSmsTestSmsDetail(err.message);
    }
  }, [apiClient, smsTestRecipient, showToast]);

  // --- Analysis Job History (real backend read, survives refresh) --
  // Loads from GET /api/v1/analysis instead of leaving jobHistory as the
  // empty useState([]) initializer forever on a page reload. Jobs created
  // in the simulated-engine fallback (tagged `simulated: true`) are never
  // persisted to the backend, so they will not reappear after a refresh --
  // only real backend-recorded jobs survive, which is the honest behavior.
  const fetchJobHistory = useCallback(async () => {
    try {
      const jobs = await apiClient.listAnalysisJobs({ limit: 50 });
      setJobHistory(jobs);
    } catch {
      // Backend unavailable or no jobs yet -- leave whatever is already in
      // jobHistory (e.g. a result from this session) rather than clearing
      // it, since this is a background refresh, not the initial load.
    }
  }, [apiClient]);

  useEffect(() => {
    fetchJobHistory();
  }, [fetchJobHistory]);

  // --- Audit Log (real backend read, survives refresh) --------------
  // Session events (responder CRUD, dispatch send/preview, SMS config
  // changes, incident status changes, analysis job completion/failure) --
  // distinct from jobHistory above (one row per analysis job). Loads from
  // GET /api/v1/audit; every record there was written by a real action's
  // own call site, never fabricated.
  const [auditLog, setAuditLog] = useState([]);
  const fetchAuditLog = useCallback(async () => {
    try {
      const entries = await apiClient.listAuditLog({ limit: 50 });
      setAuditLog(entries);
    } catch {
      // Leave whatever is already loaded rather than clearing it on a
      // transient refresh failure.
    }
  }, [apiClient]);

  useEffect(() => {
    fetchAuditLog();
  }, [fetchAuditLog]);

  // --- Responder Registry & Field Personnel Handlers ---------------
  const fetchRegisteredResponders = useCallback(async () => {
    setIsLoadingResponders(true);
    try {
      const list = await apiClient.getResponders();
      setRegisteredResponders(list);
      if (list.length > 0) {
        setSelectedTrackerResponderId(prev => prev || list[0].id);
      }
    } catch {
      setRegisteredResponders([]);
    } finally {
      setIsLoadingResponders(false);
    }
  }, [apiClient]);

  // Initial load + Periodic Polling (every 6 seconds, no WebSockets)
  useEffect(() => {
    fetchRegisteredResponders();
    const pollTimer = setInterval(() => {
      fetchRegisteredResponders();
    }, 6000);
    return () => clearInterval(pollTimer);
  }, [fetchRegisteredResponders]);

  // URL Route Detection for Mobile Duty: /responder/duty/:token
  useEffect(() => {
    const handleUrlRoute = () => {
      const pathname = window.location.pathname;
      const hash = window.location.hash;
      const searchParams = new URLSearchParams(window.location.search);
      
      let token = null;
      if (pathname.startsWith('/responder/duty/')) {
        token = pathname.replace('/responder/duty/', '').split('/')[0].trim();
      } else if (hash.startsWith('#/responder/duty/')) {
        token = hash.replace('#/responder/duty/', '').split('/')[0].trim();
      } else if (searchParams.get('duty_token') || searchParams.get('token')) {
        token = (searchParams.get('duty_token') || searchParams.get('token')).trim();
      }

      if (token) {
        setDutyToken(token);
        setView('duty');
      }
    };

    handleUrlRoute();
    window.addEventListener('popstate', handleUrlRoute);
    window.addEventListener('hashchange', handleUrlRoute);
    return () => {
      window.removeEventListener('popstate', handleUrlRoute);
      window.removeEventListener('hashchange', handleUrlRoute);
    };
  }, []);

  // Format masked mobile number: e.g. +91••••1234
  const maskPhoneNumber = (phone) => {
    if (!phone) return 'NOT CONFIGURED';
    const clean = phone.trim();
    if (clean.length <= 4) return '••••';
    const last4 = clean.slice(-4);
    const prefix = clean.startsWith('+') ? clean.slice(0, 3) : '';
    return `${prefix}••••${last4}`;
  };

  // Add Officer Submission
  const handleAddOfficerSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!addOfficerForm.name?.trim()) {
      setAddOfficerError('Officer Name is required.');
      return;
    }
    if (!addOfficerForm.username?.trim()) {
      setAddOfficerError('Username is required for duty-page login.');
      return;
    }
    if (!addOfficerForm.password || addOfficerForm.password.length < 8) {
      setAddOfficerError('Password must be at least 8 characters.');
      return;
    }
    setIsSubmittingOfficer(true);
    setAddOfficerError(null);
    try {
      const payload = {
        name: addOfficerForm.name.trim(),
        id: addOfficerForm.id?.trim() || undefined,
        phone_number: addOfficerForm.phone_number?.trim() || '',
        role: addOfficerForm.role?.trim() || 'Police Officer',
        unit: addOfficerForm.unit?.trim() || '',
        status: 'available',
        username: addOfficerForm.username.trim(),
        password: addOfficerForm.password
      };
      const created = await apiClient.createResponder(payload);
      showToast(`Officer '${payload.name}' registered.`);
      setShowAddOfficerModal(false);
      setAddOfficerForm({ name: '', id: '', phone_number: '', role: 'Police Officer', unit: '', username: '', password: '' });
      // Shown once -- the raw password is never recoverable after this.
      setCreatedOfficerCredentials({
        name: created?.name || payload.name,
        username: created?.username || payload.username,
        password: created?.password || payload.password
      });
      await fetchRegisteredResponders();
    } catch (err) {
      setAddOfficerError(err.message || 'Failed to register officer. Please check inputs.');
    } finally {
      setIsSubmittingOfficer(false);
    }
  };

  // Delete Officer
  const handleDeleteOfficer = async (officerId, officerName) => {
    if (!window.confirm(`Delete field officer '${officerName || officerId}' from active records?`)) return;
    setPersonnelDeletingId(officerId);
    try {
      await apiClient.deleteResponder(officerId);
      showToast(`Officer '${officerName || officerId}' deleted.`);
      await fetchRegisteredResponders();
    } catch (err) {
      showToast(`Failed to delete officer: ${err.message}`);
    } finally {
      setPersonnelDeletingId(null);
    }
  };

  // Send Duty Link Modal handlers
  const handleOpenSendDutyLinkModal = (officer) => {
    setSendDutyLinkModalOfficer(officer);
    setDutyLinkOutcome(null);
  };

  const handleConfirmSendDutyLink = async () => {
    if (!sendDutyLinkModalOfficer) return;
    setIsSendingDutyLink(true);
    setDutyLinkOutcome(null);
    try {
      const res = await apiClient.sendDutyLink(sendDutyLinkModalOfficer.id);
      setDutyLinkOutcome({
        success: true,
        message: 'DUTY LINK SENT',
        detail: `SMS successfully transmitted to ${maskPhoneNumber(sendDutyLinkModalOfficer.phone_number || sendDutyLinkModalOfficer.phone)}.`,
        duty_url: res.duty_url
      });
      showToast('DUTY LINK SENT');
    } catch (err) {
      setDutyLinkOutcome({
        success: false,
        message: 'DUTY LINK NOT SENT',
        error: err.message || 'Gateway transmission rejected.'
      });
      showToast('DUTY LINK NOT SENT');
    } finally {
      setIsSendingDutyLink(false);
    }
  };

  // Mobile Responder Duty - Load Officer Details by Token (display info
  // only -- never used to grant duty access; that requires a real login,
  // below). Also checks localStorage for a persisted session for this
  // officer id ("stay logged in") and attempts to resume it silently.
  useEffect(() => {
    if (view !== 'duty' || !dutyToken) return;
    let isMounted = true;
    const loadDutyOfficer = async () => {
      setDutyLoading(true);
      setDutyError(null);
      try {
        const officer = await apiClient.getDutyOfficer(dutyToken);
        if (isMounted) {
          if (officer) {
            setDutyOfficer(officer);
            if (officer.latitude != null && officer.longitude != null) {
              setDutyGpsData({
                latitude: officer.latitude,
                longitude: officer.longitude,
                accuracy_meters: officer.accuracy_meters,
                last_seen_at: officer.last_seen_at
              });
            }
          } else {
            setDutyOfficer({
              id: dutyToken,
              name: `Officer (${dutyToken})`,
              role: 'Field Responder',
              status: 'offline'
            });
          }
        }
      } catch (err) {
        if (isMounted) setDutyError(err.message || 'Failed to resolve officer profile.');
      } finally {
        if (isMounted) setDutyLoading(false);
      }
    };
    loadDutyOfficer();

    // Resume a persisted login for this officer id, if one exists. A
    // stored token that's since been stopped/expired server-side simply
    // fails on first real use (location/stop) -- handled there, not here.
    try {
      const stored = window.localStorage.getItem(`sentinelx_duty_session_${dutyToken}`);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed?.dutyToken) {
          setDutySessionToken(parsed.dutyToken);
          setDutyIsActive(true);
        }
      }
    } catch {
      // Corrupt/inaccessible localStorage entry -- fall back to login form.
    }

    return () => { isMounted = false; };
  }, [view, dutyToken, apiClient]);

  // Mobile Duty - Seconds Since Last GPS Telemetry Update
  useEffect(() => {
    if (!dutyGpsData?.last_seen_at) return;
    const updateDiff = () => {
      try {
        const last = new Date(dutyGpsData.last_seen_at).getTime();
        const diff = Math.max(0, Math.floor((Date.now() - last) / 1000));
        setDutySecondsSinceUpdate(diff);
      } catch {
        setDutySecondsSinceUpdate(0);
      }
    };
    updateDiff();
    const interval = setInterval(updateDiff, 1000);
    return () => clearInterval(interval);
  }, [dutyGpsData?.last_seen_at]);

  // Mobile Duty - Login Handler. Must succeed before any duty controls are
  // usable -- this is what turns the (unsigned, guessable) URL id into a
  // real, authenticated, trackable duty session.
  const handleDutyLogin = async (e) => {
    if (e) e.preventDefault();
    if (!dutyLoginForm.username?.trim() || !dutyLoginForm.password) {
      setDutyLoginError('Username and password are required.');
      return;
    }
    setDutyLoginSubmitting(true);
    setDutyLoginError(null);
    try {
      const result = await apiClient.loginResponder({
        username: dutyLoginForm.username.trim(),
        password: dutyLoginForm.password
      });
      setDutySessionToken(result.duty_token);
      // Deliberately NOT setting dutyIsActive(true) here. Logging in only
      // authenticates and starts the server-side duty session record --
      // it must not skip straight past the START DUTY button, since that
      // button is also what triggers the browser's actual location
      // permission prompt (see handleStartDuty's watchPosition call
      // below). The officer should land on a page that still shows
      // "START DUTY" / allow-location after logging in, and only flips to
      // "ON DUTY" once they've explicitly started GPS sharing.
      setDutyOfficer(prev => ({
        ...(prev || {}),
        id: result.responder_id,
        name: result.name || prev?.name,
        role: result.role || prev?.role,
        unit: result.unit || prev?.unit
      }));
      try {
        window.localStorage.setItem(
          `sentinelx_duty_session_${dutyToken}`,
          JSON.stringify({ dutyToken: result.duty_token, responderId: result.responder_id })
        );
      } catch {
        // localStorage unavailable (e.g. private browsing) -- login still
        // works for this page load, just won't persist across reloads.
      }
      setDutyLoginForm({ username: '', password: '' });
    } catch (err) {
      setDutyLoginError(err.message || 'Login failed. Check your username and password.');
    } finally {
      setDutyLoginSubmitting(false);
    }
  };

  // Mobile Duty - Start Duty Handler (begins GPS streaming once logged in;
  // the duty *session* itself is already active server-side as of login)
  const handleStartDuty = async () => {
    if (!dutySessionToken) return;
    setDutyError(null);
    setDutyGpsErrorDetail(null);
    setDutyLocationStatus('waiting');
    setDutyIsActive(true);

    if (typeof window === 'undefined' || !navigator.geolocation) {
      setDutyLocationStatus('unavailable');
      setDutyGpsErrorDetail('Geolocation is not supported by your browser.');
      return;
    }

    if (dutyWatchIdRef.current !== null) {
      navigator.geolocation.clearWatch(dutyWatchIdRef.current);
    }

    dutyWatchIdRef.current = navigator.geolocation.watchPosition(
      async (pos) => {
        const coords = {
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy_meters: pos.coords.accuracy,
          timestamp: new Date().toISOString()
        };

        try {
          await apiClient.updateDutyLocation(dutySessionToken, coords);
          setDutyLocationStatus('live');
          setDutyGpsData({
            latitude: coords.latitude,
            longitude: coords.longitude,
            accuracy_meters: coords.accuracy_meters,
            last_seen_at: coords.timestamp
          });
          setDutyGpsErrorDetail(null);
        } catch (postErr) {
          setDutyLocationStatus('error');
          setDutyGpsErrorDetail(`Location update failed: ${postErr.message}`);
        }
      },
      (err) => {
        if (err.code === err.PERMISSION_DENIED) {
          setDutyLocationStatus('permission_denied');
          setDutyGpsErrorDetail('LOCATION PERMISSION DENIED: Please enable location permission in your browser.');
        } else if (err.code === err.POSITION_UNAVAILABLE) {
          setDutyLocationStatus('unavailable');
          setDutyGpsErrorDetail('LOCATION UNAVAILABLE: Waiting for GPS...');
        } else if (err.code === err.TIMEOUT) {
          setDutyLocationStatus('unavailable');
          setDutyGpsErrorDetail('GPS TIMEOUT: Location request timed out.');
        } else {
          setDutyLocationStatus('error');
          setDutyGpsErrorDetail(`GPS Error: ${err.message}`);
        }
      },
      {
        enableHighAccuracy: true,
        maximumAge: 5000,
        timeout: 15000
      }
    );
  };

  // Mobile Duty - Stop Duty Handler. Ends the server-side session and
  // clears the persisted login -- the officer must log in again to start
  // a new shift, per the operator's "stay logged in only while on duty"
  // expectation.
  const handleStopDuty = async () => {
    const officerId = dutyOfficer?.id;
    try {
      if (officerId) {
        await apiClient.endDuty(officerId);
      }
    } catch {
      // ignore -- still clear local state below so the UI doesn't get stuck
    }

    if (dutyWatchIdRef.current !== null) {
      navigator.geolocation.clearWatch(dutyWatchIdRef.current);
      dutyWatchIdRef.current = null;
    }

    try {
      window.localStorage.removeItem(`sentinelx_duty_session_${dutyToken}`);
    } catch {
      // ignore
    }

    setDutyIsActive(false);
    setDutySessionToken(null);
    setDutyLocationStatus('not_sharing');
  };

  // Field Assistant Deterministic Answers
  const getFieldAssistantAnswer = (query) => {
    const q = (query || '').toLowerCase().trim();
    if (q.includes('start') || q.includes('how to start') || q.includes('begin duty')) {
      return "To start duty:\n1. Tap the green [ START DUTY ] button at the top of your screen.\n2. When prompted by your browser, tap 'Allow' for location access.\n3. Once satellite lock is acquired, coordinates stream live to SENTINEL-X Command.";
    }
    if (q.includes('stop') || q.includes('end duty') || q.includes('stop location')) {
      return "To stop location sharing:\n1. Tap the red [ STOP DUTY ] button.\n2. Location tracking will immediately stop and your status will change to OFF DUTY.\n\n⚠️ Note: The assistant explains procedures only; you must tap the [ STOP DUTY ] button directly to execute.";
    }
    if (q.includes('live') || q.includes('sharing') || q.includes('is my location live')) {
      if (dutyLocationStatus === 'live') {
        const acc = dutyGpsData.accuracy_meters != null ? `±${dutyGpsData.accuracy_meters.toFixed(1)}m` : 'High';
        return `🟢 YES — Your location is LIVE and accepted by backend.\nAccuracy: ${acc}\nLast update: ${dutySecondsSinceUpdate} sec ago.`;
      } else if (dutyLocationStatus === 'waiting') {
        return "🟡 WAITING — Waiting for GPS satellite lock. Ensure device has clear sky view.";
      } else if (dutyLocationStatus === 'permission_denied') {
        return "🔴 LOCATION PERMISSION DENIED — Please enable location permission in your browser.";
      } else if (dutyLocationStatus === 'unavailable') {
        return "🔴 LOCATION UNAVAILABLE — Waiting for GPS...";
      } else {
        return "⚫ LOCATION SHARING STOPPED — You are currently OFF DUTY.";
      }
    }
    if (q.includes('duty status') || q.includes('status') || q.includes('am i on duty')) {
      return dutyIsActive
        ? `🟢 Current Status: ON DUTY\nUnit is active on the dispatch matrix.`
        : `🔴 Current Status: OFF DUTY\nUnit is off shift. Press [ START DUTY ] to begin.`;
    }
    if (q.includes('why is location unavailable') || q.includes('unavailable') || q.includes('gps problem') || q.includes('error')) {
      return "Troubleshooting Location:\n1. Ensure Android Location / GPS toggle is enabled.\n2. In Chrome, tap URL lock icon -> Permissions -> Location -> Allow.\n3. Move away from dense metal structures or underground areas.\n4. Disable battery saver restricting background location.";
    }
    return "SENTINEL-X Field Assistant:\nI can answer questions regarding starting duty, stopping location, checking live telemetry, and troubleshooting. Select a quick prompt below or tap [ START DUTY ] / [ STOP DUTY ] directly.";
  };

  const handleSendFieldAssistantMessage = (userText) => {
    const text = (userText || dutyAssistantInput).trim();
    if (!text) return;
    const userMsg = { sender: 'user', text };
    const answer = getFieldAssistantAnswer(text);
    const botMsg = { sender: 'assistant', text: answer };
    setDutyAssistantMessages(prev => [...prev, userMsg, botMsg]);
    setDutyAssistantInput('');
  };

  const getResponderDistanceStr = useCallback((responder) => {
    if (!responder) return 'Unknown';
    if (responder.distance_km != null) return `${responder.distance_km.toFixed(2)} km`;
    const rLat = responder.lat != null ? responder.lat : responder.latitude;
    const rLng = responder.lng != null ? responder.lng : responder.longitude;
    if (selectedSource?.lat != null && selectedSource?.lng != null && rLat != null && rLng != null) {
      const d = haversineDistanceKm(selectedSource.lat, selectedSource.lng, rLat, rLng);
      return `${d.toFixed(2)} km`;
    }
    return 'Distance: Unknown';
  }, [selectedSource]);

  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return 'Recently';
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);
      if (diffSec < 5) return 'Just now';
      if (diffSec < 60) return `${diffSec} sec ago`;
      const diffMin = Math.floor(diffSec / 60);
      if (diffMin < 60) return `${diffMin} min ago`;
      return date.toLocaleTimeString();
    } catch {
      return 'Recently';
    }
  };

  const openDispatchModal = useCallback(async () => {
    setShowDispatchModal(true);
    setSelectedResponderForDispatch(null);
    setDispatchOutcome(null);
    setIsLoadingNearby(true);
    try {
      // /dispatch/eligible (not /dispatch/nearby) -- nearby deliberately
      // ignores duty status (it answers "who is geographically close",
      // on duty or not), which is why an officer who had already clicked
      // STOP DUTY could still show up here while their last GPS fix was
      // still fresh. eligible cross-checks the live duty_session, so an
      // off-duty responder drops out of this list immediately.
      const { responders } = await apiClient.getEligibleResponders({
        lat: selectedSource?.lat,
        lng: selectedSource?.lng
      });
      setNearbyResponders((responders || []).filter((r) => r.on_duty));
    } catch {
      setNearbyResponders([]);
    } finally {
      setIsLoadingNearby(false);
    }
  }, [apiClient, selectedSource]);

  const handleSelectResponderForDispatch = useCallback(async (responder) => {
    setSelectedResponderForDispatch(responder);
    setDispatchOutcome(null);

    const evStart = lastEvidenceWindow?.startTime ?? lastEvidenceWindow?.start ?? activeJob?.result?.evidence_window?.start ?? activeJob?.result?.evidence_start_sec;
    const evEnd = lastEvidenceWindow?.endTime ?? lastEvidenceWindow?.end ?? activeJob?.result?.evidence_window?.end ?? activeJob?.result?.evidence_end_sec;
    const evRange = (evStart != null && evEnd != null)
      ? `${Number(evStart).toFixed(2)}s–${Number(evEnd).toFixed(2)}s`
      : (activeJob?.result?.temporal_anomaly_window
          ? `${Number(activeJob.result.temporal_anomaly_window[0]).toFixed(2)}s–${Number(activeJob.result.temporal_anomaly_window[1]).toFixed(2)}s`
          : '16.75s–24.75s');

    // The backend result rarely carries a human-readable location string
    // (`location`/`camera_location` are usually absent), but the camera the
    // operator is actually looking at (`selectedSource`) always has its own
    // configured zone + coordinates -- fall back to those before giving up,
    // so the preview text doesn't say "NOT AVAILABLE" while the distance
    // math two lines below is working fine off the same camera's lat/lng.
    const cameraLocFallback = selectedSource?.location
      || (selectedSource?.lat != null && selectedSource?.lng != null
          ? `${Number(selectedSource.lat).toFixed(4)}, ${Number(selectedSource.lng).toFixed(4)}`
          : null);
    const actualLoc = activeJob?.result?.location || activeJob?.result?.camera_location || activeJob?.location || cameraLocFallback || null;
    const locStr = actualLoc || 'LOCATION NOT AVAILABLE';
    const confVal = activeJob?.result?.action_confidence != null
      ? activeJob.result.action_confidence
      : (activeJob?.result?.anomaly_probability || 0.572);
    const confPct = `${(Number(confVal) * (confVal <= 1 ? 100 : 1)).toFixed(1)}%`;
    const incType = activeJob?.result?.likely_action || 'Abuse';

    const defaultPreview = `SENTINEL-X INCIDENT ALERT\n\nType: ${incType}\n\nConfidence: ${confPct}\n\nLocation: ${locStr}\n\nEvidence: ${evRange}`;

    try {
      const preview = await apiClient.previewDispatch({
        responder_id: responder.id,
        incident_type: incType,
        confidence: confVal,
        location: actualLoc,
        // Camera's configured location IS the incident location -- backend
        // schema already supports these, just never populated until now.
        latitude: selectedSource?.lat,
        longitude: selectedSource?.lng,
        evidence_window: evRange,
        job_id: activeJob?.jobId
      });
      setDispatchPreviewMessage(preview.preview_text || preview.message || defaultPreview);
    } catch {
      setDispatchPreviewMessage(defaultPreview);
    }
  }, [apiClient, lastEvidenceWindow, activeJob]);

  const handleSendDispatch = useCallback(async () => {
    if (!selectedResponderForDispatch) return;
    setIsSendingDispatch(true);
    setDispatchOutcome(null);

    const evStart = lastEvidenceWindow?.startTime ?? lastEvidenceWindow?.start ?? activeJob?.result?.evidence_window?.start ?? activeJob?.result?.evidence_start_sec;
    const evEnd = lastEvidenceWindow?.endTime ?? lastEvidenceWindow?.end ?? activeJob?.result?.evidence_window?.end ?? activeJob?.result?.evidence_end_sec;
    const evRange = (evStart != null && evEnd != null)
      ? `${Number(evStart).toFixed(2)}s–${Number(evEnd).toFixed(2)}s`
      : (activeJob?.result?.temporal_anomaly_window
          ? `${Number(activeJob.result.temporal_anomaly_window[0]).toFixed(2)}s–${Number(activeJob.result.temporal_anomaly_window[1]).toFixed(2)}s`
          : '16.75s–24.75s');

    // Same camera-location fallback as handleSelectResponderForDispatch above
    // -- keep both in sync if this logic changes.
    const cameraLocFallback = selectedSource?.location
      || (selectedSource?.lat != null && selectedSource?.lng != null
          ? `${Number(selectedSource.lat).toFixed(4)}, ${Number(selectedSource.lng).toFixed(4)}`
          : null);
    const actualLoc = activeJob?.result?.location || activeJob?.result?.camera_location || activeJob?.location || cameraLocFallback || null;
    const confVal = activeJob?.result?.action_confidence != null
      ? activeJob.result.action_confidence
      : (activeJob?.result?.anomaly_probability || 0.572);
    const incType = activeJob?.result?.likely_action || 'Abuse';

    try {
      const result = await apiClient.sendDispatch({
        responder_id: selectedResponderForDispatch.id,
        recipient: selectedResponderForDispatch.phone || selectedResponderForDispatch.phone_number,
        message: dispatchPreviewMessage,
        incident_type: incType,
        confidence: confVal,
        location: actualLoc,
        latitude: selectedSource?.lat,
        longitude: selectedSource?.lng,
        evidence_window: evRange,
        job_id: activeJob?.jobId
      });

      if (result.success !== false && !result.error) {
        setDispatchOutcome({
          status: 'success',
          message: result.message || 'SMS DISPATCHED: Alert received by responder.'
        });
        showToast('SMS DISPATCHED');
      } else {
        setDispatchOutcome({
          status: 'error',
          error: result.error || result.message || 'DISPATCH FAILED: Gateway transmission rejected.'
        });
        showToast('DISPATCH FAILED');
      }
    } catch (err) {
      setDispatchOutcome({
        status: 'error',
        error: err.message || 'DISPATCH FAILED: Network or server error.'
      });
      showToast('DISPATCH FAILED');
    } finally {
      setIsSendingDispatch(false);
    }
  }, [apiClient, selectedResponderForDispatch, dispatchPreviewMessage, lastEvidenceWindow, activeJob, showToast]);

  // Refreshes the responder roster (same call already used elsewhere) so
  // the LIVE GPS map reflects the latest real locations officers' own
  // phones have reported via the duty-session flow. Read-only -- never
  // sends a location anywhere.
  const refreshTrackerLocations = useCallback(async () => {
    try {
      const list = await apiClient.getResponders();
      if (Array.isArray(list)) {
        setRegisteredResponders(list);
      }
    } catch {
      // ignore network error on refresh; keep showing last-known data
    }
  }, [apiClient]);

  // Looks up the most recent successful "dispatch_sent" audit entry for a
  // responder to find the incident location they were last dispatched to.
  // This is the audit log doing double duty as the assignment record,
  // since no separate persistent assignment table exists (see
  // send_dispatch's docstring on the backend). Returns null if the
  // responder has no qualifying dispatch on record, or the lookup fails.
  const findAssignedIncidentForResponder = useCallback(async (responderId) => {
    if (!responderId) return null;
    try {
      const entries = await apiClient.listAuditLog({ limit: 50, eventType: 'dispatch_sent' });
      if (!Array.isArray(entries)) return null;
      const match = entries.find(
        (e) => e.details && e.details.responder_id === responderId
          && e.details.incident_latitude != null && e.details.incident_longitude != null
      );
      if (!match) return null;
      return {
        latitude: match.details.incident_latitude,
        longitude: match.details.incident_longitude,
        label: match.details.incident_location_label || match.details.incident_type || 'Incident',
        timestamp: match.timestamp,
      };
    } catch {
      return null;
    }
  }, [apiClient]);

  // Fetches a real road route between two points from Mapbox's Directions
  // API, returning a GeoJSON LineString geometry (lng/lat pairs, Mapbox's
  // native order) ready to hand to L.geoJSON. Returns null on any failure
  // (missing token, no route found, network error) -- callers fall back
  // to a straight line in that case.
  const fetchMapboxRoute = useCallback(async (fromLat, fromLng, toLat, toLng) => {
    const token = import.meta.env.VITE_MAPBOX_TOKEN;
    if (!token) return null;
    try {
      const url = `https://api.mapbox.com/directions/v5/mapbox/driving/${fromLng},${fromLat};${toLng},${toLat}?geometries=geojson&overview=full&access_token=${token}`;
      const res = await fetch(url);
      if (!res.ok) return null;
      const data = await res.json();
      const route = data?.routes?.[0];
      if (!route?.geometry) return null;
      return route.geometry;
    } catch {
      return null;
    }
  }, []);

  const handleRegisterResponder = useCallback(async (e) => {
    e?.preventDefault();
    if (!newResponderForm.name.trim()) {
      showToast('Responder name is required.');
      return;
    }
    setIsRegisteringResponder(true);
    try {
      const created = await apiClient.createResponder({
        id: `RESP-${Date.now().toString().slice(-6)}`,
        name: newResponderForm.name.trim(),
        unit: newResponderForm.unit.trim() || 'Tactical Unit',
        role: newResponderForm.role.trim() || 'Patrol Officer',
        phone: newResponderForm.phone.trim() || '',
        status: 'AVAILABLE'
      });
      setNewResponderForm({ name: '', unit: '', role: '', phone: '' });
      await fetchRegisteredResponders();
      showToast(`Responder ${created.name || 'registered'} successfully.`);
    } catch (err) {
      showToast(`Failed to register responder: ${err.message}`);
    } finally {
      setIsRegisteringResponder(false);
    }
  }, [apiClient, newResponderForm, fetchRegisteredResponders, showToast]);

  const handleDeleteResponder = useCallback(async (id) => {
    try {
      await apiClient.deleteResponder(id);
      await fetchRegisteredResponders();
      showToast('Responder removed.');
    } catch (err) {
      showToast(`Failed to delete responder: ${err.message}`);
    }
  }, [apiClient, fetchRegisteredResponders, showToast]);

  // Active Job Status Polling (Every 2.5 seconds)
  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed' || activeJob.jobId === 'INITIALIZING') {
      return;
    }

    let isSubscribed = true;

    const pollJobStatus = async () => {
      if (simulatedEngineMode || activeJob.jobId.startsWith('JOB-SIM-')) {
        setTimeout(() => {
          if (!isSubscribed) return;
          if (activeJob.status === 'queued') {
            setActiveJob(prev => ({ ...prev, status: 'processing' }));
          } else if (activeJob.status === 'processing') {
            const isAnomaly = activeJob.system === 'anomaly';

            let mockResult;
            if (isAnomaly) {
              mockResult = {
                job_id: activeJob.jobId,
                status: 'completed',
                system_type: 'anomaly',
                simulated: true,
                anomaly_detected: true,
                anomaly_status: 'DETECTED',
                anomaly_probability: 0.884,
                likely_action: 'Perimeter Fence Breach / Climbing',
                action_confidence: 0.932,
                processing_time_seconds: 3.18,
                action_candidates: [
                  { class_name: 'Perimeter Fence Breach / Climbing', probability: 0.932 },
                  { class_name: 'Loitering at Gate Boundary', probability: 0.051 },
                  { class_name: 'Object Dropping / Foreign Item', probability: 0.012 },
                  { class_name: 'Normal Walking Motion', probability: 0.005 }
                ],
                model_info: {
                  stage1_name: 'final_binary_detector_v1',
                  stage2_name: 'action_classifier_v2',
                  i3d_backbone: 'rgb_imagenet'
                },
                temporal_evidence: {
                  available: true,
                  window_duration_seconds: 8.0,
                  windows: [
                    { window_index: 0, start_time_seconds: 0.0, end_time_seconds: 8.0, stage1_attention_normalized: 0.12, stage2_attention_normalized: 0.18 },
                    { window_index: 1, start_time_seconds: 4.0, end_time_seconds: 12.0, stage1_attention_normalized: 0.45, stage2_attention_normalized: 0.65 },
                    { window_index: 2, start_time_seconds: 8.0, end_time_seconds: 16.0, stage1_attention_normalized: 1.0, stage2_attention_normalized: 0.95 },
                    { window_index: 3, start_time_seconds: 12.0, end_time_seconds: 20.0, stage1_attention_normalized: 0.35, stage2_attention_normalized: 0.22 }
                  ]
                },
                timestamp: new Date().toISOString()
              };
            } else {
              mockResult = {
                job_id: activeJob.jobId,
                status: 'completed',
                system_type: 'vision_yolo',
                simulated: true,
                object_summary: {
                  people_count: 7,
                  vehicles_count: 3,
                  unique_tracks: 10,
                  max_persons_in_frame: 9,
                  max_vehicles_in_frame: 4
                },
                detections: [
                  { class_name: 'person', confidence: 0.94, bbox: [120, 80, 240, 380], track_id: 'TRK-001' },
                  { class_name: 'person', confidence: 0.89, bbox: [310, 110, 410, 390], track_id: 'TRK-002' },
                  { class_name: 'car', confidence: 0.96, bbox: [520, 210, 780, 410], track_id: 'TRK-003' },
                  { class_name: 'person', confidence: 0.82, bbox: [810, 95, 900, 320], track_id: 'TRK-004' }
                ],
                tracks: [
                  { track_id: 'TRK-001', class_name: 'person', duration_sec: 12.4, direction: 'North-East', confidence_avg: 0.92 },
                  { track_id: 'TRK-002', class_name: 'person', duration_sec: 9.1, direction: 'South-West', confidence_avg: 0.88 },
                  { track_id: 'TRK-003', class_name: 'car', duration_sec: 14.2, direction: 'East-Bound', confidence_avg: 0.95 }
                ],
                performance: {
                  processing_time_seconds: 1.45,
                  inference_fps: 42.8,
                  average_latency_ms: 23.4
                },
                model_info: {
                  model_name: 'YOLOv8-Enterprise-Vision',
                  device: 'NVIDIA RTX 4090 (CUDA)',
                  input_size: '640x640'
                },
                timestamp: new Date().toISOString()
              };
            }

            setActiveJob(prev => ({ ...prev, status: 'completed', result: mockResult }));
            setJobHistory(prev => [mockResult, ...prev]);
            incidentAssistant.refreshSummary();
            incidentAssistant.refreshAiSummary(true);
          }
        }, 2000);
        return;
      }

      try {
        const statusData = await apiClient.getJobStatus(activeJob.jobId);
        if (!isSubscribed) return;

        if (statusData.status === 'completed') {
          const resultData = await apiClient.getJobResult(activeJob.jobId);
          if (!isSubscribed) return;

          setActiveJob(prev => ({
            ...prev,
            status: 'completed',
            result: resultData
          }));

          setJobHistory(prev => [resultData, ...prev]);
          // This job just finished -- refresh the AI Copilot's incident
          // summary now, otherwise it keeps showing whatever was "latest"
          // as of page mount (useIncidentAssistant only auto-fetches once).
          incidentAssistant.refreshSummary();
          incidentAssistant.refreshAiSummary(true);
        } else if (statusData.status === 'failed') {
          setActiveJob(prev => ({
            ...prev,
            status: 'failed',
            error: statusData.error || 'Pipeline error encountered during neural model execution'
          }));
        } else {
          setActiveJob(prev => ({
            ...prev,
            status: statusData.status
          }));
        }
      } catch (err) {
        if (!isSubscribed) return;
        console.error('Job status polling error:', err);
      }
    };

    const intervalId = setInterval(pollJobStatus, 2500);
    pollJobStatus();

    return () => {
      isSubscribed = false;
      clearInterval(intervalId);
    };
  }, [activeJob, apiClient, simulatedEngineMode]);

  // CHANGE LOG (added this session -- see submitActiveJob's comment above
  // for the full revert steps): starts playback once the backend job has
  // actually left 'queued' (i.e. upload finished, real processing began),
  // instead of the old autoPlay-on-select behavior. Guarded so it only
  // calls .play() once per job -- re-running on every status poll tick
  // would otherwise fight the user if they manually paused.
  const playbackStartedForJobRef = useRef(null);
  useEffect(() => {
    if (!isAwaitingBackendStart || !activeJob) return;
    const isStillQueued = activeJob.status === 'queued' || activeJob.jobId === 'INITIALIZING';
    if (isStillQueued) return;
    if (playbackStartedForJobRef.current === activeJob.jobId) return;

    playbackStartedForJobRef.current = activeJob.jobId;
    setIsAwaitingBackendStart(false);
    const video = videoRef.current;
    if (video) {
      video.play().catch(() => {
        // Autoplay-with-sound/other browser restrictions -- controls are
        // still visible (the <video> keeps `controls`), so the user can
        // just press play manually; nothing else depends on this succeeding.
      });
    }
  }, [activeJob, isAwaitingBackendStart]);

  // Real-time Canvas Bounding Box Rendering
  useEffect(() => {
    if (!canvasRef.current || !videoRef.current) return;

    const canvas = canvasRef.current;
    const video = videoRef.current;
    const ctx = canvas.getContext('2d');

    let animationFrameId;

    const drawOverlay = () => {
      if (!video || video.paused || video.ended) {
        animationFrameId = requestAnimationFrame(drawOverlay);
        return;
      }

      canvas.width = video.clientWidth;
      canvas.height = video.clientHeight;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (
        analysisMode === 'vision_yolo' &&
        activeJob &&
        activeJob.status === 'completed' &&
        activeJob.result &&
        activeJob.result.detections &&
        toggleDetections
      ) {
        const videoNativeW = video.videoWidth || 1920;
        const videoNativeH = video.videoHeight || 1080;

        const scaleX = canvas.width / videoNativeW;
        const scaleY = canvas.height / videoNativeH;

        activeJob.result.detections.forEach((det) => {
          if (!det.bbox) return;

          const [x1, y1, x2, y2] = det.bbox;
          const boxX = x1 * scaleX;
          const boxY = y1 * scaleY;
          const boxW = (x2 - x1) * scaleX;
          const boxH = (y2 - y1) * scaleY;

          ctx.strokeStyle = '#3B82F6';
          ctx.lineWidth = 2;
          ctx.strokeRect(boxX, boxY, boxW, boxH);

          ctx.fillStyle = 'rgba(59, 130, 246, 0.85)';
          const labelText = `${det.class_name.toUpperCase()} ${(det.confidence * 100).toFixed(0)}%${
            toggleTracks && det.track_id ? ` [${det.track_id}]` : ''
          }`;

          ctx.font = '10px "IBM Plex Mono", monospace';
          const textMetrics = ctx.measureText(labelText);
          ctx.fillRect(boxX, boxY > 18 ? boxY - 18 : boxY, textMetrics.width + 8, 18);

          ctx.fillStyle = '#FFFFFF';
          ctx.fillText(labelText, boxX + 4, boxY > 18 ? boxY - 5 : boxY + 12);
        });
      }

      animationFrameId = requestAnimationFrame(drawOverlay);
    };

    drawOverlay();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [analysisMode, activeJob, toggleDetections, toggleTracks]);

  // Tear down the Leaflet instance whenever the modal closes. The map's
  // container div (`mapContainerRef`) lives inside `{showMapModal && (...)}`,
  // so React unmounts/remounts that whole subtree on every close/reopen --
  // but `mapInstanceRef.current` is a ref, so without this it would keep
  // pointing at the now-detached old container on the next open, leaving
  // tiles rendering into an invisible element (black screen, confirmed via
  // devtools: tiles genuinely loaded, just attached to a dead DOM node).
  // Keyed ONLY on showMapModal so this doesn't fire on every marker/source
  // update while the map is legitimately still open.
  useEffect(() => {
    if (showMapModal) return;
    if (mapResizeObserverRef.current) {
      mapResizeObserverRef.current.disconnect();
      mapResizeObserverRef.current = null;
    }
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }
    markersRef.current = [];
    tileLayerRef.current = null;
  }, [showMapModal]);

  // Leaflet Map Initialization with CartoDB Voyager API Layer
  useEffect(() => {
    if (!showMapModal || !mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      const initialLat = selectedSource.lat || 16.4022;
      const initialLng = selectedSource.lng || 74.3820;

      const map = L.map(mapContainerRef.current, {
        center: [initialLat, initialLng],
        zoom: 14,
        zoomControl: true,
        attributionControl: true
      });

      // Integrate CartoDB Voyager raster tiles with provided API key
      const voyagerLayer = L.tileLayer(CARTO_VOYAGER_TILE_URL, {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19
      }).addTo(map);

      tileLayerRef.current = voyagerLayer;
      mapInstanceRef.current = map;

      // Invalidate size once the container actually reports a real size,
      // instead of guessing a fixed delay against the modal's CSS
      // transition -- a fixed setTimeout can fire before the modal has
      // finished animating in (container still 0x0), which leaves Leaflet's
      // internal tile grid computed against zero dimensions: tiles "load"
      // (confirmed via devtools) but render in the wrong place, showing as
      // a black screen. ResizeObserver reacts to the real size change
      // whenever it actually happens, so this is correct regardless of how
      // long the modal's open transition takes.
      let invalidatedOnce = false;
      const resizeObserver = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (!entry) return;
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          map.invalidateSize();
          invalidatedOnce = true;
        }
      });
      resizeObserver.observe(mapContainerRef.current);
      mapResizeObserverRef.current = resizeObserver;
      // Belt-and-suspenders: also try the old fixed-delay call in case the
      // container was already correctly sized before the observer attached
      // (ResizeObserver only fires on a *change*, not the initial size).
      setTimeout(() => {
        if (!invalidatedOnce) map.invalidateSize();
      }, 200);
    } else {
      if (selectedSource.lat && selectedSource.lng) {
        mapInstanceRef.current.setView([selectedSource.lat, selectedSource.lng], 14);
      }
    }

    const map = mapInstanceRef.current;

    // Clear previous markers
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];

    // Camera Marker
    if (selectedSource.lat && selectedSource.lng) {
      const cameraIcon = L.divIcon({
        className: 'custom-map-icon',
        html: `<div style="width:16px;height:16px;border-radius:9999px;background:#3B82F6;border:2px solid #FFFFFF;box-shadow:0 0 12px rgba(59,130,246,0.8);"></div>`,
        iconSize: [16, 16]
      });

      const camMarker = L.marker([selectedSource.lat, selectedSource.lng], { icon: cameraIcon }).addTo(map);
      camMarker.bindPopup(`<b>${selectedSource.title}</b><br/>ID: ${selectedSource.id}<br/>Location: ${selectedSource.location}<br/>Coordinates: ${selectedSource.lat}, ${selectedSource.lng} (Nipani, Karnataka)`).openPopup();
      markersRef.current.push(camMarker);
    }

    // Sample/reference patrol markers -- NOT real backend responders. These
    // exist only to illustrate map layout before any responder is
    // registered; they are visually distinct (dashed outline + "SAMPLE"
    // prefix in the popup) and deliberately not click-selectable/
    // dispatchable (no onSelect wiring here), so a user can't mistake one
    // for a live, dispatchable unit the way the old click-to-select
    // behavior allowed. Real units come from registeredResponders /
    // nearbyResponders (fetched from the backend) and are rendered
    // separately when present.
    TACTICAL_RESPONDERS.forEach((responder) => {
      const sampleIcon = L.divIcon({
        className: 'custom-map-icon',
        html: `<div style="width:14px;height:14px;border-radius:9999px;background:transparent;border:2px dashed #64748B;"></div>`,
        iconSize: [14, 14]
      });

      const rMarker = L.marker([responder.lat, responder.lng], { icon: sampleIcon }).addTo(map);
      rMarker.bindPopup(`<b>SAMPLE DATA -- NOT A REAL UNIT</b><br/>${responder.id}<br/>${responder.unit}<br/>(illustrative map reference only)`);
      markersRef.current.push(rMarker);
    });

    // Real registered responders (from the backend), rendered as live,
    // selectable, dispatchable units -- clearly distinct styling from the
    // sample markers above.
    registeredResponders.forEach((responder) => {
      if (responder.latitude == null || responder.longitude == null) return;
      const isSelected = selectedResponder && selectedResponder.id === responder.id;
      const liveState = (responder.live_state || '').toLowerCase();
      const color = isSelected ? '#10B981' : liveState === 'live' ? '#3B82F6' : '#F59E0B';
      const responderIcon = L.divIcon({
        className: 'custom-map-icon',
        html: `<div style="width:14px;height:14px;border-radius:9999px;background:${color};border:2px solid #FFFFFF;box-shadow:0 0 10px ${color};"></div>`,
        iconSize: [14, 14]
      });

      const rMarker = L.marker([responder.latitude, responder.longitude], { icon: responderIcon }).addTo(map);
      rMarker.bindPopup(`<b>${responder.name || responder.id}</b><br/>${responder.role || ''}<br/>Status: <b>${responder.status || 'unknown'}</b><br/>Live state: ${responder.live_state || 'unknown'}`);
      rMarker.on('click', () => setSelectedResponder(responder));
      markersRef.current.push(rMarker);
    });

    return () => {
      if (!showMapModal && mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [showMapModal, selectedSource, selectedResponder, registeredResponders]);

  // LIVE GPS tab map: read-only, plots every registered responder's real
  // last-known location (reported by their own phone via the duty-session
  // flow). Same Leaflet + CartoDB Voyager setup as the main tactical map
  // modal above, kept separate since this one lives inline in the 'tracker'
  // view rather than in a modal.
  useEffect(() => {
    if (view !== 'tracker' || !trackerMapContainerRef.current) {
      if (view !== 'tracker' && trackerMapInstanceRef.current) {
        trackerMapInstanceRef.current.remove();
        trackerMapInstanceRef.current = null;
      }
      return;
    }

    if (!trackerMapInstanceRef.current) {
      const map = L.map(trackerMapContainerRef.current, {
        center: [16.4044521, 74.3790313],
        zoom: 12,
        zoomControl: true,
      });
      L.tileLayer(CARTO_VOYAGER_TILE_URL, {
        attribution: '&copy; CARTO &copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);
      trackerMapInstanceRef.current = map;

      const resizeObserver = new ResizeObserver(() => map.invalidateSize());
      resizeObserver.observe(trackerMapContainerRef.current);
    }

    const map = trackerMapInstanceRef.current;
    map.invalidateSize();

    trackerMarkersRef.current.forEach(m => m.remove());
    trackerMarkersRef.current = [];

    const located = registeredResponders.filter(
      (r) => r.latitude != null && r.longitude != null
    );

    located.forEach((responder) => {
      const liveState = (responder.live_state || '').toLowerCase();
      const status = (responder.status || '').toLowerCase();
      const isLive = liveState === 'live' && status !== 'offline';
      const color = isLive ? '#10B981' : status === 'offline' || !responder.status ? '#64748B' : '#F59E0B';

      const icon = L.divIcon({
        className: 'custom-map-icon',
        html: `<div style="width:14px;height:14px;border-radius:9999px;background:${color};border:2px solid #FFFFFF;box-shadow:0 0 10px ${color}CC;"></div>`,
        iconSize: [14, 14],
      });
      const marker = L.marker([responder.latitude, responder.longitude], { icon }).addTo(map);
      const lastUpdate = responder.last_location_update || responder.updated_at;
      marker.bindPopup(
        `<b>${responder.name || responder.id}</b><br/>${responder.role || responder.unit || 'Officer'}<br/>` +
        `Status: <b>${responder.status || 'unknown'}</b><br/>` +
        `Live: ${isLive ? 'Yes' : 'No'}<br/>` +
        (lastUpdate ? `Last update: ${new Date(lastUpdate).toLocaleTimeString()}` : '')
      );
      marker.on('click', () => setSelectedTrackerResponderId(responder.id));
      trackerMarkersRef.current.push(marker);
    });

    if (located.length > 0) {
      const bounds = L.latLngBounds(located.map(r => [r.latitude, r.longitude]));
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }

    return () => {
      if (view !== 'tracker' && trackerMapInstanceRef.current) {
        trackerMapInstanceRef.current.remove();
        trackerMapInstanceRef.current = null;
      }
    };
  }, [view, registeredResponders]);

  // Auto-refresh the responder roster every 10s while the LIVE GPS tab is
  // open, so the map reflects fresh locations without a manual reload.
  useEffect(() => {
    if (view !== 'tracker' || !trackerAutoRefresh) return;
    refreshTrackerLocations();
    const intervalId = setInterval(refreshTrackerLocations, 10000);
    return () => clearInterval(intervalId);
  }, [view, trackerAutoRefresh, refreshTrackerLocations]);

  // When a responder is selected on the LIVE GPS map, look up the incident
  // they were last dispatched to (from the audit log) and clear any stale
  // route/incident from a previously-selected responder.
  useEffect(() => {
    if (view !== 'tracker' || !selectedTrackerResponderId) {
      setTrackerAssignedIncident(null);
      setTrackerRouteError(null);
      return;
    }
    let cancelled = false;
    setTrackerAssignedIncident(null);
    setTrackerRouteError(null);
    findAssignedIncidentForResponder(selectedTrackerResponderId).then((incident) => {
      if (!cancelled) setTrackerAssignedIncident(incident);
    });
    return () => { cancelled = true; };
  }, [view, selectedTrackerResponderId, findAssignedIncidentForResponder]);

  // Draws the incident marker + route line on the tracker map once both
  // the selected responder's live location and their assigned incident
  // are known. Tries a real Mapbox road route first; falls back to a
  // straight dashed line if Mapbox fails (no token, network error, no
  // route found) so the feature still shows *something* useful.
  useEffect(() => {
    const map = trackerMapInstanceRef.current;
    if (!map || view !== 'tracker') return;

    if (trackerRouteLayerRef.current) {
      trackerRouteLayerRef.current.remove();
      trackerRouteLayerRef.current = null;
    }

    if (!trackerAssignedIncident) return;

    const responder = registeredResponders.find((r) => r.id === selectedTrackerResponderId);
    if (!responder || responder.latitude == null || responder.longitude == null) return;

    const fromLat = responder.latitude;
    const fromLng = responder.longitude;
    const toLat = trackerAssignedIncident.latitude;
    const toLng = trackerAssignedIncident.longitude;

    let cancelled = false;
    setTrackerRouteLoading(true);
    setTrackerRouteError(null);

    const incidentIcon = L.divIcon({
      className: 'custom-map-icon',
      html: `<div style="width:16px;height:16px;border-radius:3px;background:#EF4444;border:2px solid #FFFFFF;box-shadow:0 0 12px rgba(239,68,68,0.8);transform:rotate(45deg);"></div>`,
      iconSize: [16, 16],
    });
    const incidentMarker = L.marker([toLat, toLng], { icon: incidentIcon }).addTo(map);
    incidentMarker.bindPopup(`<b>Assigned Incident</b><br/>${trackerAssignedIncident.label}`);

    const drawFallbackLine = () => {
      const line = L.polyline([[fromLat, fromLng], [toLat, toLng]], {
        color: '#F59E0B', weight: 3, dashArray: '6, 8', opacity: 0.85,
      }).addTo(map);
      return L.layerGroup([incidentMarker, line]).addTo(map);
    };

    fetchMapboxRoute(fromLat, fromLng, toLat, toLng).then((geometry) => {
      if (cancelled) return;
      setTrackerRouteLoading(false);
      let layer;
      if (geometry) {
        const routeLine = L.geoJSON(geometry, {
          style: { color: '#3B82F6', weight: 4, opacity: 0.9 },
        }).addTo(map);
        layer = L.layerGroup([incidentMarker, routeLine]).addTo(map);
      } else {
        setTrackerRouteError('Road route unavailable -- showing straight-line path instead.');
        layer = drawFallbackLine();
      }
      trackerRouteLayerRef.current = layer;
      const bounds = L.latLngBounds([[fromLat, fromLng], [toLat, toLng]]);
      map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 });
    });

    return () => { cancelled = true; };
  }, [view, trackerAssignedIncident, selectedTrackerResponderId, registeredResponders, fetchMapboxRoute]);

  /* ==========================================================================
     STEP 2E: SHARED RELATIVE-ATTENTION COMPUTATION (single source of truth)
     The SAME relativeAttention = window_attention / max_window_attention_in_video
     calculation, and the SAME >= 0.70 qualifying threshold, used by both the
     Step 2B/2D attentionHUD below AND the TemporalActivityStrip rendered
     under the video. Computed once here from the real backend windows so
     neither consumer can drift into a second/conflicting threshold.
     ========================================================================== */
  // Stable half: depends ONLY on the backend result, never on currentTime --
  // safe for handleTimeUpdate's useCallback (keyed on [activeJob]) to read
  // without going stale between native timeupdate events.
  const temporalAttention = useMemo(() => {
    const jobResult = activeJob?.result;
    const windows = jobResult?.temporal_evidence?.windows;
    if (!windows || windows.length === 0) {
      return { relativeAttentionOf: () => 0 };
    }
    const windowAttention = windows.map((w) => Math.max(w.stage1_attention ?? 0, w.stage2_attention ?? 0));
    const maxAttention = Math.max(...windowAttention);
    const relativeAttentionOf = (idx) => (maxAttention > 0 ? windowAttention[idx] / maxAttention : 0);
    return { relativeAttentionOf };
  }, [activeJob?.result]);

  // NOTE: the single-track timeline (Step 2E v4) no longer needs a
  // "currently active window index" -- it renders visibleAnomalyRegions
  // (recomputed fresh every render from currentTime + segmentStart, see
  // below) instead. The old per-window active-index memo was removed;
  // attentionHUD (Step 2B/2C) still computes its own activeIdx locally from
  // the live event time, unaffected by this.

  // STEP 2E (v2): merge adjacent/overlapping QUALIFYING windows (the SAME
  // relativeAttentionOf >= 0.70 windows above) into discrete anomaly
  // intervals for the single-track timeline. Depends only on the backend
  // result + the stable relativeAttentionOf -- never on currentTime --
  // so it is safe for the reveal-latch effect below to depend on.
  const mergedAnomalyIntervals = useMemo(() => {
    const windows = activeJob?.result?.temporal_evidence?.windows;
    if (!windows || windows.length === 0) return [];
    const qualifying = windows
      .filter((_, idx) => temporalAttention.relativeAttentionOf(idx) >= 0.70)
      .sort((a, b) => a.start_time_seconds - b.start_time_seconds);
    const merged = [];
    for (const w of qualifying) {
      const last = merged[merged.length - 1];
      if (last && w.start_time_seconds <= last.end) {
        last.end = Math.max(last.end, w.end_time_seconds);
      } else {
        merged.push({ start: w.start_time_seconds, end: w.end_time_seconds });
      }
    }
    return merged;
  }, [activeJob?.result, temporalAttention]);

  // STEP 2E (v6): the latest timestamp the backend actually produced
  // temporal_evidence for. The model only ever analyzes a prefix of the
  // video (fixed-size sliding windows from t=0) -- anything past this point
  // was NEVER evaluated, so it must not be paintable as GREEN "observed, no
  // anomaly" no matter how far reachedRanges/currentTime has played past it.
  // null when there's no evidence at all (e.g. normal-video job, or a job
  // still missing temporal_evidence) -- callers treat null as "no coverage
  // limit from evidence" vs. 0 which means "evidence exists but covers
  // nothing", so the two are kept distinct rather than both defaulting to 0.
  const evidenceEndTime = useMemo(() => {
    const windows = activeJob?.result?.temporal_evidence?.windows;
    if (!windows || windows.length === 0) return null;
    return Math.max(...windows.map((w) => w.end_time_seconds ?? 0));
  }, [activeJob?.result]);

  // STEP 2E (v4): the ACTUAL regions rendered as red on the timeline, derived
  // fresh on every render from mergedAnomalyIntervals + currentTime +
  // segmentStart -- never accumulated/latched (see segmentStart's comment
  // for the full rule). visibleStart/visibleEnd per interval:
  //   visibleStart = max(interval.start, segmentStart)
  //   visibleEnd   = min(currentTime, interval.end)
  // and the interval only contributes a region when visibleEnd > visibleStart.
  const visibleAnomalyRegions = useMemo(() => {
    if (mergedAnomalyIntervals.length === 0) return [];
    const regions = [];
    for (const iv of mergedAnomalyIntervals) {
      const visibleStart = Math.max(iv.start, segmentStart);
      const visibleEnd = Math.min(currentTime, iv.end);
      if (visibleEnd > visibleStart) {
        regions.push({ start: visibleStart, end: visibleEnd });
      }
    }
    return regions;
  }, [mergedAnomalyIntervals, currentTime, segmentStart]);

  /* ==========================================================================
     STEP 2B: HONEST TEMPORAL ATTENTION HUD SYNC (relative threshold)
     Fires on every native HTML5 video `timeupdate` event. Looks up whether
     the current playback position falls inside a temporal_evidence window
     carrying this video's OWN strongest model attention, and if so surfaces
     a HUD badge. The badge NEVER displays a per-window classification -- it
     only ever repeats the whole-video likely_action / action_confidence that
     the backend already decided across the full video (same as the
     Intelligence Panel). The windows are only used to decide WHEN to show it.

     Threshold is relative, not absolute: raw per-window softmax attention
     over ~32 windows is naturally diffuse (peaks well under an arbitrary
     0.25 cutoff on real videos), so "high attention" is defined per-video as
     relativeAttention = window_attention / max_window_attention_in_this_video,
     activating at >= 0.70. This is a visualization/evidence threshold only --
     never conflated with action_confidence (a real softmax probability).

     Anomaly gate reuses the SAME existing whole-video anomaly decision the
     Intelligence Panel already uses elsewhere in this file (anomaly_detected,
     falling back to anomaly_probability > 0.5) -- no second anomaly
     threshold is invented here.
     ========================================================================== */
  const handleTimeUpdate = useCallback((e) => {
    const time = e.currentTarget.currentTime;
    setCurrentTime(time);

    const jobResult = activeJob?.result;
    const windows = jobResult?.temporal_evidence?.windows;

    // STEP 2D: the "first evidence encountered" latch belongs to THIS
    // analysis job. A brand new job (new jobId) must start the latch fresh;
    // re-renders/seeks within the same job must never reset it.
    if (encounteredJobIdRef.current !== activeJob?.jobId) {
      encounteredJobIdRef.current = activeJob?.jobId ?? null;
      setHasEncounteredEvidence(false);
      setLastEvidenceWindow(null);
      // STEP 2E (v4): a brand new job also starts the timeline's segment
      // tracking fresh -- same reset point, no second job-change detector
      // invented. This does NOT control red-reveal memory (there is none);
      // it only resets the segment left-bound used for the current job.
      setSegmentStart(0);
      // STEP 2E (v5): same reset point for the GREEN reached-coverage
      // ranges -- a new job has observed nothing yet.
      setReachedRanges([{ start: 0, end: 0 }]);
      lastKnownTimeRef.current = 0;
    }

    // STEP 2E (v4): only treat this as genuine continuous playback -- and
    // therefore safe to use as the new "last known time" baseline for the
    // NEXT seek's forward/backward classification -- when we're not in the
    // middle of a seek. A stray timeupdate between `seeking` and `seeked`
    // must never be read as real playback progression. segmentStart itself
    // is deliberately left untouched here: continuous playback never needs
    // to move its own left-bound, only seeks do (handled in handleSeeked).
    if (!isSeekingRef.current) {
      lastKnownTimeRef.current = time;
      // STEP 2E (v5): genuine continuous playback -- extend the LAST reached
      // range's end to the new time. This is the ONLY place ranges grow,
      // mirroring how segmentStart's red reveal only grows from real
      // timeupdate progression. A forward/backward seek never calls this
      // (isSeekingRef guards it out); seeks are handled entirely in
      // handleSeeked below.
      setReachedRanges(prev => {
        if (prev.length === 0) return [{ start: time, end: time }];
        const last = prev[prev.length - 1];
        if (time <= last.end) return prev; // no progress past the known edge
        const updated = prev.slice();
        updated[updated.length - 1] = { ...last, end: time };
        return updated;
      });
    }

    const isAnomaly = Boolean(
      jobResult?.anomaly_detected || (jobResult?.anomaly_probability && jobResult.anomaly_probability > 0.5)
    );

    // STEP 2E (v4): the timeline's red reveal is no longer accumulated here
    // at all -- it is derived purely at render time from currentTime +
    // segmentStart (see TemporalEvidenceTimeline / the computed
    // visibleAnomalyRegions below). Nothing to do in this handler for it.

    if (!isAnomaly || !windows || windows.length === 0) {
      setAttentionHUD({ visible: false });
      return;
    }

    // STEP 2E: reuse the SAME shared relativeAttentionOf (stable, keyed only
    // on the backend result) also consumed by the TemporalActivityStrip --
    // NOT a second/duplicate threshold. activeIdx itself is still computed
    // here from the live event `time` (not the memoized currentTime state,
    // which would be one event stale inside this callback's closure).
    const { relativeAttentionOf } = temporalAttention;

    // STEP 2C: the backend result can arrive at any wall-clock moment
    // (inference duration is processing time, NEVER an event timestamp), so
    // the strongest qualifying window is identified purely from the real
    // window data -- independent of currentTime -- and used only to label
    // the neutral "ANALYSIS READY" state while playback hasn't reached it
    // yet. Presentation activation itself still depends solely on currentTime
    // below.
    const strongIdx = windows.findIndex((_, idx) => relativeAttentionOf(idx) >= 0.70);
    const strongWindow = strongIdx !== -1 ? windows[strongIdx] : null;

    const activeIdx = windows.findIndex((w, idx) => {
      if (time < w.start_time_seconds || time > w.end_time_seconds) return false;
      return relativeAttentionOf(idx) >= 0.70;
    });

    if (activeIdx !== -1) {
      const activeEvidence = windows[activeIdx];
      // STEP 2D: latch permanently once ANY qualifying window is reached.
      // Never reset by leaving the window -- only a new jobId resets it
      // (handled above). lastEvidenceWindow is overwritten (not cleared) on
      // every active window so "EVIDENCE WINDOW PASSED" always reflects the
      // most recently active real window.
      setHasEncounteredEvidence(true);
      setLastEvidenceWindow({
        startTime: activeEvidence.start_time_seconds,
        endTime: activeEvidence.end_time_seconds
      });
      setAttentionHUD({
        visible: true,
        label: 'TEMPORAL MODEL EVIDENCE',
        wholeVideoAction: jobResult.likely_action,
        wholeVideoConfidence: jobResult.action_confidence != null
          ? (jobResult.action_confidence * 100).toFixed(1)
          : null,
        startTime: activeEvidence.start_time_seconds,
        endTime: activeEvidence.end_time_seconds,
        relativeAttention: (relativeAttentionOf(activeIdx) * 100).toFixed(0),
        nextWindowStart: activeEvidence.start_time_seconds,
        nextWindowEnd: activeEvidence.end_time_seconds
      });
    } else {
      setAttentionHUD({
        visible: false,
        // Carried for the neutral "ANALYSIS READY" state only -- never used
        // to activate the incident presentation itself.
        nextWindowStart: strongWindow ? strongWindow.start_time_seconds : null,
        nextWindowEnd: strongWindow ? strongWindow.end_time_seconds : null
      });
    }
  }, [activeJob, temporalAttention, mergedAnomalyIntervals]);

  /* ==========================================================================
     STEP 2E (v4): SEEK CLASSIFICATION -- native `seeking`/`seeked` events.
     These are the ONLY place segmentStart ever moves. See the segmentStart
     comment near its declaration for the full rule. Kept intentionally
     separate from handleTimeUpdate/Step 2D -- this purely maintains the
     timeline's own playback-segment bookkeeping and never touches
     hasEncounteredEvidence/lastEvidenceWindow/the Intelligence Panel.
     ========================================================================== */
  const handleSeeking = useCallback(() => {
    isSeekingRef.current = true;
  }, []);

  const handleSeeked = useCallback((e) => {
    isSeekingRef.current = false;
    const newTime = e.currentTarget.currentTime;
    const previousTime = lastKnownTimeRef.current;

    if (newTime < previousTime) {
      // Backward seek: always safe to reset to 0. Rewinding never fakes a
      // new claim -- currentTime itself already hides anything ahead of the
      // new position, so treating this like a fresh pass from 0 only ever
      // RESTORES legitimate historical coverage behind the new position,
      // never invents any.
      setSegmentStart(0);
    } else if (newTime > previousTime) {
      // Forward seek: the skipped gap must never be claimed as observed, so
      // nothing before the landing point can count toward any interval.
      setSegmentStart(newTime);
      // STEP 2E (v5): a seek is NOT playback -- the skipped [previousTime,
      // newTime) gap must never render green either. Close off the current
      // reached range where it actually stopped (it already stopped
      // growing once the seek began, since handleTimeUpdate ignores
      // mid-seek events) and start a brand new zero-width range at the
      // landing point. Nothing covers the gap, so it falls through to the
      // DARK "not yet reached" default.
      setReachedRanges(prev => [...prev, { start: newTime, end: newTime }]);
    }
    // newTime === previousTime: no real jump, nothing to reclassify.

    lastKnownTimeRef.current = newTime;
  }, []);

  // Shared by handleSelectSource/handleFileUpload: resets every piece of
  // per-video-source state when the user switches to a different video,
  // so a video the user returns to later (same file re-selected, or a
  // demo feed re-picked) is treated as unanalyzed and genuinely
  // re-submitted, and no evidence/timeline state from the PREVIOUS video
  // can still be visible while the new one is pending/loading.
  //
  // currentAnalyzedSourceKeyRef is the critical one: handleVideoPlay's
  // "only submit once per source" guard (below) is write-only -- it is
  // set when a job is submitted for a source, but was never being cleared
  // on source switch. That meant re-selecting an already-analyzed source
  // later in the same session silently skipped resubmission entirely (no
  // POST /api/v1/analysis at all), leaving the video to "just play" with
  // no job and no result. Clearing it here is the actual fix.
  //
  // The rest (hasEncounteredEvidence/lastEvidenceWindow/segmentStart/
  // reachedRanges/encounteredJobIdRef/lastKnownTimeRef) were already
  // correctly reset reactively on the new job's first timeupdate (see the
  // encounteredJobIdRef check further down) -- resetting them here too is
  // proactive, not a behavior change, and removes any window where stale
  // evidence/timeline state could render before that first timeupdate.
  const resetPerSourceState = () => {
    currentAnalyzedSourceKeyRef.current = null;
    setActiveJob(null);
    setCurrentTime(0);
    setDuration(null);
    setHasEncounteredEvidence(false);
    setLastEvidenceWindow(null);
    setSegmentStart(0);
    setReachedRanges([{ start: 0, end: 0 }]);
    encounteredJobIdRef.current = null;
    lastKnownTimeRef.current = 0;
  };

  /* ==========================================================================
     AUTOMATIC ANALYSIS TRIGGER (STEP 2A -> submit-before-playback revision)
     CHANGED this session: submission used to live in handleVideoPlay and
     fire on the HTML5 "play" event, with autoPlay starting playback (and
     therefore the timeline's clock) in the same instant the job was still
     being uploaded/queued -- a slow upload meant the timeline raced ahead
     of a job that hadn't actually started yet (all green, then a late
     result retroactively paints it). submitActiveJob now fires immediately
     on source selection, BEFORE playback starts; the effect further below
     (search "start playback once backend actually begins processing")
     starts the video once the job leaves 'queued'. To revert: move this
     body back inside handleVideoPlay, call it from the <video onPlay=...>
     handler instead of handleSelectSource/handleFileUpload, delete that
     later effect, and restore `autoPlay` on the main <video> element.
     Guarded: only runs ONCE per video source, regardless of pause/resume/seek.
     ========================================================================== */
  const submitActiveJob = useCallback(async (sourceId, file, videoUrl, sourceInfo) => {
    const currentSourceKey = file
      ? `file_${file.name}_${file.size}_${file.lastModified}`
      : sourceId;

    // Guard: Do not submit multiple analysis jobs for the same source
    if (currentAnalyzedSourceKeyRef.current === currentSourceKey) {
      return;
    }

    // Stash this source's video URL + location under its temporary key
    // immediately, keyed the same way the submission guard above is --
    // re-keyed onto the real job_id once the backend assigns one (below).
    // Lets the Session Events audit view later recover "what did this
    // incident look like" for a job still live in this browser session.
    jobSourceInfoRef.current[currentSourceKey] = {
      videoUrl,
      lat: sourceInfo?.lat ?? null,
      lng: sourceInfo?.lng ?? null,
      locationLabel: sourceInfo?.locationLabel ?? null,
      sourceTitle: sourceInfo?.sourceTitle ?? null,
    };

    // Set guard immediately
    currentAnalyzedSourceKeyRef.current = currentSourceKey;
    setIsAwaitingBackendStart(true);

    setActiveJob({
      jobId: 'INITIALIZING',
      status: 'queued',
      result: null,
      error: null,
      system: analysisMode,
      startTime: new Date().toLocaleTimeString()
    });

    if (!apiHealth.connected && !simulatedEngineMode) {
      setActiveJob({
        jobId: `JOB-SIM-${Date.now().toString().slice(-6)}`,
        status: 'queued',
        result: null,
        error: null,
        system: analysisMode,
        startTime: new Date().toLocaleTimeString()
      });
      setSimulatedEngineMode(true);
      return;
    }

    try {
      let response;
      if (file) {
        response = await apiClient.submitAnalysis({ file, systemType: analysisMode });
      } else {
        response = await apiClient.submitAnalysis({ videoUrl, systemType: analysisMode });
      }

      const realJobId = response.job_id || `JOB-${Math.floor(Math.random() * 90000 + 10000)}`;

      // Re-key the stashed source info from the temporary submission-guard
      // key onto the real job_id, so later audit-log lookups (which only
      // know the job_id, from the dispatch_sent audit entry's `details`)
      // can find it.
      if (jobSourceInfoRef.current[currentSourceKey]) {
        jobSourceInfoRef.current[realJobId] = jobSourceInfoRef.current[currentSourceKey];
      }

      setActiveJob({
        jobId: realJobId,
        status: response.status || 'queued',
        result: null,
        error: null,
        system: analysisMode,
        startTime: new Date().toLocaleTimeString()
      });
    } catch (err) {
      setIsAwaitingBackendStart(false);
      setActiveJob({
        jobId: 'ERROR',
        status: 'failed',
        result: null,
        error: err.message || 'Failed to trigger job on backend API',
        system: analysisMode,
        startTime: new Date().toLocaleTimeString()
      });
    }
  }, [analysisMode, apiHealth.connected, simulatedEngineMode, apiClient]);

  const handleSelectSource = (source) => {
    setSelectedSource(source);
    setCustomFile(null);
    setVideoPreviewUrl(source.videoUrl);
    resetPerSourceState();
    submitActiveJob(source.id, null, source.videoUrl, {
      lat: source.lat,
      lng: source.lng,
      locationLabel: source.location,
      sourceTitle: source.title,
    });
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCustomFile(file);
    const fileUrl = URL.createObjectURL(file);
    setVideoPreviewUrl(fileUrl);
    const newSourceId = `USER-UPLOAD-${Date.now()}`;
    setSelectedSource({
      id: newSourceId,
      title: file.name,
      type: analysisMode,
      location: incidentLocation.label,
      resolution: `${(file.size / (1024 * 1024)).toFixed(1)} MB Video File`,
      status: 'Custom File',
      sampleName: file.name,
      lat: incidentLocation.lat,
      lng: incidentLocation.lng
    });
    resetPerSourceState();
    submitActiveJob(newSourceId, file, fileUrl, {
      lat: incidentLocation.lat,
      lng: incidentLocation.lng,
      locationLabel: incidentLocation.label,
      sourceTitle: file.name,
    });
  };

  // No longer submits -- kept as a harmless no-op so the existing
  // <video onPlay={handleVideoPlay}> wiring doesn't need to change.
  // Submission now happens in submitActiveJob (see above), triggered on
  // source selection rather than on the play event.
  const handleVideoPlay = useCallback(() => {}, []);

  const handleDispatchAlert = async (responderId = 'PATROL-NIPANI-01') => {
    const activeJobId = activeJob?.jobId || 'INC-MANUAL-DISPATCH';
    await apiClient.sendNotificationSMS(activeJobId, {
      unit: responderId,
      location: selectedSource.location,
      severity: 'CRITICAL',
      timestamp: new Date().toISOString()
    });

    showToast(`🚨 DISPATCH SENT: Unit ${responderId} mobilized to ${selectedSource.location}`);
    if (showMapModal) setShowMapModal(false);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    showToast('Copied payload to clipboard.');
  };

  return (
    <div className="min-h-screen bg-[#08090C] text-slate-200 flex flex-col font-sans antialiased selection:bg-blue-600">
      
      {/* GLOBAL TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="fixed top-16 right-4 z-50 bg-[#151822] border border-blue-500/80 px-4 py-2.5 rounded-sm shadow-2xl text-xs font-mono text-white flex items-center gap-2 animate-bounce">
          <Icons.CheckCircle className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* HEADER / NAVIGATION BAR */}
      <header className="h-14 bg-[#0D0E13] border-b border-[#1E2232] px-4 flex items-center justify-between shrink-0 z-40">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setView('landing')}
            className="flex items-center gap-2.5 text-left focus:outline-none group"
          >
            <div className="w-8 h-8 rounded-sm bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 group-hover:bg-blue-600 group-hover:text-white transition-all">
              <Icons.Shield className="w-4 h-4" />
            </div>
            <div>
              <div className="font-mono font-bold text-xs tracking-wider text-white flex items-center gap-2">
                <span>SENTINEL-X</span>
                <span className="text-[10px] text-blue-400 bg-blue-500/10 border border-blue-500/20 px-1.5 py-0.2 rounded-sm font-normal">v2.4 COPILOT</span>
              </div>
              <div className="text-[10px] text-slate-400 font-mono">Tactical AI Vision &amp; Threat Terminal</div>
            </div>
          </button>

          <div className="h-4 w-[1px] bg-[#1E2232] hidden sm:block"></div>

          {/* View Navigation Tabs */}
          <nav className="hidden sm:flex items-center gap-1 text-xs font-mono">
            <button
              onClick={() => setView('landing')}
              className={`px-3 py-1.5 rounded-sm transition-colors ${
                view === 'landing' 
                  ? 'bg-[#151822] text-white font-semibold border border-[#2B3148]' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              LANDING
            </button>
            <button
              onClick={() => setView('analysis')}
              className={`px-3 py-1.5 rounded-sm transition-colors ${
                view === 'analysis'
                  ? 'bg-[#151822] text-white font-semibold border border-[#2B3148]'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              ANALYSIS WORKSPACE
            </button>

            {/* FIELD PERSONNEL TAB */}
            <button
              onClick={() => setView('personnel')}
              className={`px-3 py-1.5 rounded-sm transition-colors flex items-center gap-1.5 ${
                view === 'personnel' 
                  ? 'bg-emerald-600/20 text-emerald-400 font-semibold border border-emerald-500/50' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              <Icons.Users className="w-3.5 h-3.5 text-emerald-400" />
              <span>FIELD PERSONNEL</span>
              {registeredResponders.length > 0 && (
                <span className="px-1.5 py-0.2 text-[9px] font-bold rounded-sm bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {registeredResponders.length}
                </span>
              )}
            </button>

            {/* GPS RESPONDER TRACKER TAB */}
            <button
              onClick={() => setView('tracker')}
              className={`px-3 py-1.5 rounded-sm transition-colors flex items-center gap-1.5 ${
                view === 'tracker' 
                  ? 'bg-blue-600/20 text-blue-400 font-semibold border border-blue-500/50' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              <Icons.Radio className="w-3.5 h-3.5 text-blue-400" />
              <span>LIVE GPS</span>
            </button>

            <button
              onClick={() => setView('logs')}
              className={`px-3 py-1.5 rounded-sm transition-colors ${
                view === 'logs' 
                  ? 'bg-[#151822] text-white font-semibold border border-[#2B3148]' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
              }`}
            >
              AUDIT TRAIL ({jobHistory.length})
            </button>
          </nav>
        </div>

        {/* Right Action Bar */}
        <div className="flex items-center gap-3 font-mono text-xs">
          {/* Tactical Map Trigger Button */}
          <button
            onClick={() => setShowMapModal(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-sm bg-[#151822] hover:bg-[#1B202E] border border-blue-500/40 text-blue-400 hover:text-white transition-colors"
            title="Open Tactical Map (CartoDB Voyager)"
          >
            <Icons.Map className="w-3.5 h-3.5" />
            <span className="hidden md:inline">MAP (VOYAGER)</span>
          </button>

          {/* API Status Badge (Status indicator only -- not clickable) */}
          <div 
            className={`flex items-center gap-2 px-2.5 py-1 rounded-sm border cursor-default select-none transition-all ${
              apiHealth.connected 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                : simulatedEngineMode 
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
            }`}
            title={`FastAPI Backend Status: ${apiHealth.connected ? 'Connected (Port 8000)' : 'Offline'}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${
              apiHealth.connected ? 'bg-emerald-400 animate-pulse' : simulatedEngineMode ? 'bg-amber-400' : 'bg-rose-400'
            }`}></span>
            <span className="text-[11px] font-semibold tracking-wide">
              {apiHealth.checking ? 'PINGING...' : apiHealth.connected ? 'API CONNECTED' : simulatedEngineMode ? 'SIMULATED ENGINE' : 'API OFFLINE'}
            </span>
          </div>

          {/* Primary Settings Entrypoint (Full-page Workspace) */}
          <button
            onClick={() => view === 'settings' ? closeSettings() : openSettings()}
            className={`p-1.5 rounded-sm transition-all border ${
              view === 'settings'
                ? 'bg-blue-600/20 text-blue-400 border-blue-500/50 shadow-sm shadow-blue-500/20'
                : 'text-slate-400 hover:text-white bg-[#151822] hover:bg-[#1B202E] border-[#232838]'
            }`}
            title={view === 'settings' ? 'Return to Command' : 'Open System Configuration / Settings'}
          >
            <Icons.Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex flex-col overflow-hidden">
        
        {/* VIEW 1: LANDING HERO */}
        {view === 'landing' && (
          <div className="flex-1 flex flex-col justify-between p-6 lg:p-12 max-w-7xl mx-auto w-full bg-tech-grid">
            
            <div className="my-auto py-12 space-y-8 max-w-4xl">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-sm bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono">
                <Icons.Cpu className="w-3.5 h-3.5" />
                <span>TACTICAL THREAT INTELLIGENCE &amp; AI CHATBOT TERMINAL</span>
              </div>

              <div className="space-y-4">
                <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white font-sans leading-tight">
                  Enterprise Video Intelligence &amp; <span className="text-blue-400">AI Copilot</span>
                </h1>
                <p className="text-slate-400 text-sm sm:text-base leading-relaxed font-normal max-w-2xl">
                  Real-time video threat classification, YOLO object tracking, CartoDB geospatial mapping, and an integrated tactical SOC AI Chatbot assistant built for rapid incident response and log analysis.
                </p>
              </div>

              {/* Multi Mode Chooser Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                
                {/* Anomaly Card */}
                <div 
                  onClick={() => {
                    setAnalysisMode('anomaly');
                    setView('analysis');
                  }}
                  className="p-5 bg-[#0D0E13] border border-[#1E2232] hover:border-blue-500/80 rounded-sm cursor-pointer transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-sm bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
                      <Icons.Shield className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 bg-[#151822] px-1.5 py-0.5 rounded-sm border border-[#232838]">STAGE 1 &amp; 2</span>
                  </div>
                  <h3 className="text-sm font-bold text-white font-mono">ANOMALY ENGINE</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                    Detect security fence breaches and unauthorized access using Swin3D classifiers.
                  </p>
                </div>

                {/* Vision YOLO Card */}
                <div 
                  onClick={() => {
                    setAnalysisMode('vision_yolo');
                    setView('analysis');
                  }}
                  className="p-5 bg-[#0D0E13] border border-[#1E2232] hover:border-indigo-500/80 rounded-sm cursor-pointer transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-sm bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center">
                      <Icons.Crosshair className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono text-slate-400 bg-[#151822] px-1.5 py-0.5 rounded-sm border border-[#232838]">YOLO DETECTOR</span>
                  </div>
                  <h3 className="text-sm font-bold text-white font-mono">VISION TRACKING</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                    Extract bounding box detections, counts, unique track IDs, and movement vectors.
                  </p>
                </div>

                {/* AI Copilot Card -- routes to the Analysis Workspace,
                    where AI COPILOT now lives as an embedded tab next to
                    DETECTION DATA (see components/dashboard-panel/). */}
                <div
                  onClick={() => setView('analysis')}
                  className="p-5 bg-[#0D0E13] border border-blue-500/40 hover:border-blue-400 rounded-sm cursor-pointer transition-all bg-gradient-to-br from-blue-950/20 to-transparent"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="w-8 h-8 rounded-sm bg-blue-500/20 border border-blue-400 text-blue-300 flex items-center justify-center">
                      <Icons.Bot className="w-4 h-4" />
                    </div>
                    <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded-sm border border-blue-500/30">AI COPILOT</span>
                  </div>
                  <h3 className="text-sm font-bold text-white font-mono">AI INCIDENT SUMMARY</h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed font-sans">
                    A Grok-generated summary of the latest incident, available in the Analysis Workspace.
                  </p>
                </div>

              </div>

              {/* Primary CTA Buttons */}
              <div className="flex flex-wrap items-center gap-4 pt-4 border-t border-[#1E2232]">
                <button
                  onClick={() => setView('analysis')}
                  className="px-6 py-2.5 rounded-sm bg-blue-600 hover:bg-blue-500 text-white font-mono font-semibold text-xs tracking-wider flex items-center gap-2 transition-all shadow-lg shadow-blue-600/20"
                >
                  <Icons.Bot className="w-4 h-4" />
                  <span>OPEN AI COPILOT</span>
                </button>
                <button
                  onClick={() => setView('analysis')}
                  className="px-6 py-2.5 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-slate-200 font-mono text-xs border border-[#232838] transition-all"
                >
                  OPEN VIDEO WORKSPACE
                </button>
                <button
                  onClick={() => setShowMapModal(true)}
                  className="px-6 py-2.5 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-blue-400 font-mono text-xs border border-blue-500/40 flex items-center gap-2 transition-all"
                >
                  <Icons.Map className="w-4 h-4" />
                  <span>OPEN CARTODB VOYAGER MAP</span>
                </button>
              </div>
            </div>

            {/* Footer Specs Bar */}
            <div className="bg-[#0D0E13] border border-[#1E2232] p-3 rounded-sm flex flex-col sm:flex-row items-center justify-between gap-2 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-2">
                <Icons.Server className="w-4 h-4 text-blue-400" />
                <span>BACKEND API: <strong className="text-slate-200">{backendUrl}</strong></span>
              </div>
              <div className="flex items-center gap-2">
                <Icons.Map className="w-4 h-4 text-emerald-400" />
                <span>MAP TILES: <strong className="text-slate-200">CartoDB Voyager (Active)</strong></span>
              </div>
            </div>

          </div>
        )}

        {/* VIEW 3: ANALYSIS WORKSPACE */}
        {view === 'analysis' && (
          <div className="flex-1 flex flex-col lg:flex-row overflow-hidden bg-[#08090C]">
            
            {/* LEFT SIDEBAR: Source Feeds & Custom Upload */}
            <div className="w-full lg:w-72 bg-[#0D0E13] border-r border-[#1E2232] p-4 flex flex-col gap-4 shrink-0 overflow-y-auto">
              
              {/* System Switcher Header */}
              <div>
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block mb-2">
                  ANALYSIS ENGINE MODE
                </span>
                <div className="grid grid-cols-2 gap-1 bg-[#151822] p-1 rounded-sm border border-[#232838]">
                  <button
                    onClick={() => {
                      setAnalysisMode('anomaly');
                      setActiveJob(null);
                    }}
                    className={`py-1.5 px-2 rounded-sm text-[11px] font-mono transition-all ${
                      analysisMode === 'anomaly' 
                        ? 'bg-blue-600 text-white font-bold' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    ANOMALY
                  </button>
                  <button
                    onClick={() => {
                      setAnalysisMode('vision_yolo');
                      setActiveJob(null);
                    }}
                    className={`py-1.5 px-2 rounded-sm text-[11px] font-mono transition-all ${
                      analysisMode === 'vision_yolo' 
                        ? 'bg-blue-600 text-white font-bold' 
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    VISION / YOLO
                  </button>
                </div>
              </div>

              <div className="h-[1px] bg-[#1E2232]"></div>

              {/* Available Feeds */}
              <div className="space-y-2">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
                  FEED SOURCES
                </span>

                {DEMO_VIDEO_SOURCES.map((source) => {
                  const isSelected = selectedSource.id === source.id && !customFile;
                  return (
                    <div
                      key={source.id}
                      onClick={() => handleSelectSource(source)}
                      className={`p-2.5 rounded-sm border cursor-pointer font-mono transition-all ${
                        isSelected
                          ? 'bg-[#151822] border-blue-500/80 text-white'
                          : 'bg-[#11131A] border-[#1E2232] hover:border-slate-700 text-slate-300'
                      }`}
                    >
                      <video
                        src={source.videoUrl}
                        autoPlay
                        loop
                        muted
                        playsInline
                        preload="metadata"
                        className="w-full h-10 object-cover rounded-sm mb-1.5 opacity-90"
                      />
                      <div className="flex items-center justify-between text-[10px] text-blue-400 font-bold">
                        <span>{source.id}</span>
                        <span className="text-emerald-400">{source.status}</span>
                      </div>
                      <div className="text-xs font-bold text-slate-100 mt-1 font-sans truncate">{source.title}</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">{source.resolution}</div>
                    </div>
                  );
                })}
              </div>

              {/* Custom Upload Dropzone */}
              <div className="space-y-2 pt-2">
                <span className="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider block">
                  UPLOAD VIDEO FILE
                </span>
                <label className="border border-dashed border-[#232838] hover:border-blue-500 bg-[#11131A] hover:bg-[#151822] p-3 rounded-sm flex flex-col items-center justify-center cursor-pointer transition-all text-center">
                  <Icons.Upload className="w-4 h-4 text-blue-400 mb-1" />
                  <span className="text-xs font-mono font-medium text-slate-300">Select MP4 / AVI File</span>
                  <span className="text-[10px] text-slate-500 font-mono mt-0.5">Automatic analysis on playback</span>
                  <input 
                    type="file" 
                    accept="video/*" 
                    onChange={handleFileUpload} 
                    className="hidden" 
                  />
                </label>
              </div>

            </div>

            {/* MAIN ANALYSIS CONTENT AREA */}
            <div className="flex-1 flex flex-col xl:flex-row overflow-hidden bg-[#08090C]">
              
              {/* 70% VIDEO & PLAYBACK AREA */}
              <div className="w-full xl:w-[70%] flex flex-col p-4 lg:p-6 overflow-y-auto border-r border-[#1E2232]">
                
                {/* Top Feed Info Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#1E2232]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-bold text-white font-mono uppercase">{selectedSource.title}</h2>
                      <span className="text-[10px] bg-[#151822] text-slate-300 font-mono px-1.5 py-0.5 rounded-sm border border-[#232838]">
                        {selectedSource.id}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">
                      Location: {selectedSource.location} &bull; Target Engine: <span className="text-blue-400">{analysisMode === 'anomaly' ? 'ANOMALY CLASSIFIER (AUTO-TRIGGER)' : 'YOLO DETECTOR (AUTO-TRIGGER)'}</span>
                    </p>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center gap-2">
                    {customFile ? (
                      <button
                        onClick={() => {
                          setIncidentLocationLinkInput('');
                          setIncidentLocationError(null);
                          setShowIncidentLocationModal(true);
                        }}
                        className="px-3 py-2 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-blue-400 border border-blue-500/40 font-mono text-xs flex items-center gap-1.5 transition-colors"
                      >
                        <Icons.Settings className="w-3.5 h-3.5" />
                        <span>SET INCIDENT LOCATION</span>
                      </button>
                    ) : (
                      <button
                        onClick={() => setShowMapModal(true)}
                        className="px-3 py-2 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-blue-400 border border-blue-500/40 font-mono text-xs flex items-center gap-1.5 transition-colors"
                      >
                        <Icons.Map className="w-3.5 h-3.5" />
                        <span>GEOLOCATE (VOYAGER)</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* YOLO Bounding Box Toggles */}
                {analysisMode === 'vision_yolo' && (
                  <div className="flex items-center gap-4 py-2 text-xs font-mono text-slate-400">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={toggleDetections} 
                        onChange={(e) => setToggleDetections(e.target.checked)} 
                        className="rounded-sm bg-[#11131A] border-[#232838] text-blue-600 focus:ring-0" 
                      />
                      <span>Show Bounding Boxes</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={toggleTracks} 
                        onChange={(e) => setToggleTracks(e.target.checked)} 
                        className="rounded-sm bg-[#11131A] border-[#232838] text-blue-600 focus:ring-0" 
                      />
                      <span>Show Track IDs</span>
                    </label>
                  </div>
                )}

                {/* UNINTERRUPTED VIDEO CONTAINER (NO OVERLAYS COVERING PLAYBACK) */}
                <div className="mt-2 relative rounded-sm overflow-hidden bg-black border border-[#1E2232] flex items-center justify-center min-h-[380px] lg:min-h-[480px]">

                  <video
                    ref={videoRef}
                    key={videoPreviewUrl}
                    src={videoPreviewUrl}
                    controls
                    playsInline
                    onPlay={handleVideoPlay}
                    onTimeUpdate={handleTimeUpdate}
                    onSeeking={handleSeeking}
                    onSeeked={handleSeeked}
                    onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
                    className="w-full h-full object-contain max-h-[580px]"
                  ></video>

                  {/* CHANGE LOG (added this session, see submitActiveJob's
                      comment for the full revert steps): loading overlay
                      shown while the job is still queued/uploading, so
                      playback (and therefore the timeline's clock) doesn't
                      start until the backend actually begins processing. */}
                  {isAwaitingBackendStart && (
                    <div className="absolute inset-0 z-30 bg-black/85 flex flex-col items-center justify-center gap-3 text-slate-300 font-mono text-xs">
                      <div className="w-8 h-8 border-2 border-slate-600 border-t-sky-400 rounded-full animate-spin" />
                      <span>UPLOADING TO ANALYSIS PIPELINE…</span>
                    </div>
                  )}

                  {/* Canvas Overlay for YOLO Bounding Boxes (Pointer events none) */}
                  <canvas 
                    ref={canvasRef} 
                    className="absolute inset-0 pointer-events-none z-10 w-full h-full"
                  />

                  {/* HUD Overlay Badge */}
                  <div className="absolute top-3 left-3 bg-black/80 px-2.5 py-1 rounded-sm text-[10px] font-mono text-emerald-400 border border-emerald-500/30 flex items-center gap-2 z-20 pointer-events-none">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>FEED ACTIVE // {selectedSource.id}</span>
                  </div>

                  {/* STEP 2B: TEMPORAL ATTENTION HUD -- appears only while
                      currentTime is inside this video's strongest relative-
                      attention window AND the whole-video result is an
                      anomaly. Always reports the whole-video action/
                      confidence (authoritative), with model attention shown
                      as a separately-labeled relative evidence score --
                      never phrased as a probability or as a per-window
                      classification. */}
                  {attentionHUD.visible && (
                    <div className="absolute top-3 right-3 bg-black/85 px-3 py-2 rounded-sm text-[10px] font-mono text-rose-400 border border-rose-500/50 flex flex-col gap-1 z-20 pointer-events-none max-w-[260px] animate-pulse">
                      <div className="flex items-center gap-2 font-bold tracking-wide">
                        <Icons.AlertTriangle className="w-3.5 h-3.5" />
                        <span>&#9888; {attentionHUD.label}</span>
                      </div>
                      <div className="text-slate-200 font-sans normal-case font-normal">
                        <div className="text-[9px] text-slate-400 uppercase">Likely Action</div>
                        <span className="text-rose-300 font-bold uppercase">{attentionHUD.wholeVideoAction}</span>
                        {attentionHUD.wholeVideoConfidence != null && (
                          <span className="text-slate-400"> &bull; {attentionHUD.wholeVideoConfidence}% action confidence</span>
                        )}
                      </div>
                      <div className="text-[9px] text-slate-400">
                        <span className="text-slate-500 uppercase">Evidence Window</span> {attentionHUD.startTime.toFixed(1)}s&mdash;{attentionHUD.endTime.toFixed(1)}s
                      </div>
                      <div className="text-[9px] text-slate-400">
                        <span className="text-slate-500 uppercase">Model Attention</span> {attentionHUD.relativeAttention}% <span className="text-slate-500">(relative, not a probability)</span>
                      </div>
                    </div>
                  )}

                </div>

                {/* STEP 2E (v3): VIDEO ACTIVITY TIMELINE -- shell depends ONLY on
                    video.duration (handled inside the component itself), never
                    on activeJob/analysis state. Analysis result only ever adds
                    the red revealed-anomaly regions on top. */}
                <TemporalEvidenceTimeline
                  currentTime={currentTime}
                  duration={duration}
                  videoRef={videoRef}
                  visibleRegions={visibleAnomalyRegions}
                  reachedRanges={reachedRanges}
                  evidenceEndTime={evidenceEndTime}
                  isAnomaly={Boolean(
                    activeJob?.result?.anomaly_detected ||
                      (activeJob?.result?.anomaly_probability && activeJob.result.anomaly_probability > 0.5)
                  )}
                />

              </div>

              {/* RIGHT PANEL: AI COPILOT / DETECTION DATA tab strip --
                  components/dashboard-panel/DashboardRightPanel.jsx. DETECTION
                  DATA renders AnalysisResultsPanel unchanged (same props this
                  file already owned); AI COPILOT renders the real Grok-backed
                  incident summarizer. */}
              <DashboardRightPanel
                activeJob={activeJob}
                duration={duration}
                currentTime={currentTime}
                hasEncounteredEvidence={hasEncounteredEvidence}
                lastEvidenceWindow={lastEvidenceWindow}
                attentionHUD={attentionHUD}
                selectedSource={selectedSource}
                openDispatchModal={openDispatchModal}
                aiSummary={incidentAssistant.aiSummary}
                aiSummaryLoading={incidentAssistant.aiSummaryLoading}
                aiSummaryError={incidentAssistant.aiSummaryError}
                refreshAiSummary={incidentAssistant.refreshAiSummary}
              />

            </div>

          </div>
        )}

        {/* VIEW 4: AUDIT TRAIL LOGS -- ONE unified, clickable table.
            Backed by `auditLog` (the real, persisted backend audit_logs
            collection -- survives a refresh, unlike jobHistory which is
            just this browser session's in-memory AnalysisResult list).
            Rows for analysis jobs (event_type starting "analysis_job_")
            are enriched with that job's score/confidence/duration from
            jobHistory when a matching entry is still in memory -- a nice-
            to-have, never required: the row is still fully clickable and
            correct without it. Every row opens the same detail modal
            (place / officer+phone / confidence / clip) used for dispatch
            events; other event types show whatever their own `details`
            actually carries. */}
        {view === 'logs' && (
          <div className="flex-1 p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6 overflow-y-auto font-mono">
            <div className="flex items-center justify-between pb-4 border-b border-[#1E2232]">
              <div>
                <h1 className="text-lg font-bold text-white uppercase">Incident &amp; Analysis Audit Logs</h1>
                <p className="text-xs text-slate-400 mt-0.5">Real recorded backend events -- click any row for full details. Never fabricated.</p>
              </div>
              <span className="text-xs text-slate-400 bg-[#151822] px-3 py-1 rounded-sm border border-[#232838]">
                TOTAL EVENTS: {auditLog.length}
              </span>
            </div>

            <div className="bg-[#0D0E13] border border-[#1E2232] rounded-sm overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-[#151822] border-b border-[#1E2232] text-slate-400 text-[10px] uppercase">
                      <th className="p-3">Event</th>
                      <th className="p-3">Module</th>
                      <th className="p-3">Resource</th>
                      <th className="p-3">Outcome</th>
                      <th className="p-3">Summary</th>
                      <th className="p-3">Confidence</th>
                      <th className="p-3">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1E2232] text-slate-300">
                    {auditLog.length === 0 ? (
                      <tr>
                        <td colSpan="7" className="p-8 text-center text-slate-500 font-mono">
                          No audit events recorded yet.
                        </td>
                      </tr>
                    ) : (
                      auditLog.map((entry) => {
                        // Enrichment only -- matches this audit entry to a
                        // still-in-memory jobHistory item by job_id, purely
                        // to show a confidence number inline. Falls back to
                        // the entry's own details.confidence (dispatch
                        // events carry this directly), then nothing.
                        const matchingJob = jobHistory.find(
                          (j) => j.job_id && (j.job_id === entry.resource_id || j.job_id === entry.details?.job_id)
                        );
                        const confidence = entry.details?.confidence != null
                          ? entry.details.confidence
                          : matchingJob?.anomaly_probability ?? matchingJob?.action_confidence ?? null;
                        return (
                          <tr
                            key={entry.event_id}
                            onClick={() => setSelectedAuditEntry(entry)}
                            className="hover:bg-[#11131A] cursor-pointer"
                            title="Click for full details"
                          >
                            <td className="p-3 text-blue-400 font-bold">{entry.event_type}</td>
                            <td className="p-3 uppercase text-slate-400">{entry.module || '—'}</td>
                            <td className="p-3 text-slate-300">
                              {entry.resource_type ? `${entry.resource_type}:${entry.resource_id || '?'}` : '—'}
                            </td>
                            <td className={`p-3 font-bold ${entry.outcome === 'failure' ? 'text-rose-400' : 'text-emerald-400'}`}>
                              {entry.outcome.toUpperCase()}
                            </td>
                            <td className="p-3 font-sans text-slate-300">{entry.summary || '—'}</td>
                            <td className="p-3 text-emerald-400">
                              {confidence != null ? `${(confidence <= 1 ? confidence * 100 : confidence).toFixed(1)}%` : '—'}
                            </td>
                            <td className="p-3 text-slate-500 text-[10px]">{entry.timestamp}</td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* VIEW: FIELD PERSONNEL / OFFICER MANAGEMENT */}
        {view === 'personnel' && (
          <div className="flex-1 p-4 lg:p-8 max-w-7xl mx-auto w-full space-y-6 overflow-y-auto font-mono text-xs">
            {/* Header / Title Bar */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#1E2232] gap-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-sm bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                    <Icons.Users className="w-4 h-4" />
                  </div>
                  <div>
                    <h1 className="text-lg font-bold text-white uppercase tracking-wider">FIELD PERSONNEL</h1>
                    <div className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
                      <span className="font-bold text-emerald-400">
                        {registeredResponders.length} {registeredResponders.length === 1 ? 'OFFICER' : 'OFFICERS'}
                      </span>
                      <span>•</span>
                      <span>Live GPS Telemetry &amp; Field Duty Dispatch Registry</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2.5">
                <button
                  onClick={fetchRegisteredResponders}
                  disabled={isLoadingResponders}
                  className="px-3 py-1.5 bg-[#151822] hover:bg-[#1F2434] text-slate-300 hover:text-white rounded-sm border border-[#232838] flex items-center gap-1.5 transition-colors"
                  title="Query /api/v1/responders"
                >
                  <Icons.RefreshCw className={`w-3.5 h-3.5 ${isLoadingResponders ? 'animate-spin text-emerald-400' : ''}`} />
                  <span>REFRESH</span>
                </button>

                <button
                  onClick={() => {
                    setAddOfficerForm({ name: '', id: '', phone_number: '', role: 'Police Officer', unit: '' });
                    setAddOfficerError(null);
                    setShowAddOfficerModal(true);
                  }}
                  className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-sm flex items-center gap-1.5 transition-colors shadow-md shadow-emerald-600/20 uppercase"
                >
                  <Icons.Plus className="w-4 h-4" />
                  <span>ADD OFFICER</span>
                </button>
              </div>
            </div>

            {/* Quick Metrics Bar */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-[#0D0E13] border border-[#1E2232] p-3.5 rounded-sm">
                <div className="text-[10px] text-slate-500 uppercase font-bold">TOTAL REGISTERED</div>
                <div className="text-xl font-bold text-white mt-1">{registeredResponders.length}</div>
              </div>
              <div className="bg-[#0D0E13] border border-[#1E2232] p-3.5 rounded-sm">
                <div className="text-[10px] text-emerald-500 uppercase font-bold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span>LOCATION LIVE</span>
                </div>
                <div className="text-xl font-bold text-emerald-400 mt-1">
                  {registeredResponders.filter(r => (r.live_state || '').toLowerCase() === 'live' && (r.status || '').toLowerCase() !== 'offline').length}
                </div>
              </div>
              <div className="bg-[#0D0E13] border border-[#1E2232] p-3.5 rounded-sm">
                <div className="text-[10px] text-blue-500 uppercase font-bold">ON DUTY</div>
                <div className="text-xl font-bold text-blue-400 mt-1">
                  {registeredResponders.filter(r => (r.status || '').toLowerCase() === 'available' || (r.status || '').toLowerCase() === 'busy' || (r.status || '').toLowerCase() === 'on_duty').length}
                </div>
              </div>
              <div className="bg-[#0D0E13] border border-[#1E2232] p-3.5 rounded-sm">
                <div className="text-[10px] text-slate-500 uppercase font-bold">OFF DUTY</div>
                <div className="text-xl font-bold text-slate-400 mt-1">
                  {registeredResponders.filter(r => (r.status || '').toLowerCase() === 'offline' || !r.status).length}
                </div>
              </div>
            </div>

            {/* Filter and Search Bar */}
            <div className="bg-[#0D0E13] border border-[#1E2232] p-3 rounded-sm flex flex-col sm:flex-row items-center justify-between gap-3">
              {/* Search */}
              <div className="w-full sm:w-72">
                <input
                  type="text"
                  value={personnelSearch}
                  onChange={(e) => setPersonnelSearch(e.target.value)}
                  placeholder="Search by name, ID, role, or unit..."
                  className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-1.5 text-white font-mono text-xs focus:outline-none placeholder:text-slate-600"
                />
              </div>

              {/* Status Filters */}
              <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto">
                {['ALL', 'LIVE', 'ON_DUTY', 'OFF_DUTY'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setPersonnelFilter(f)}
                    className={`px-2.5 py-1 rounded-sm text-[11px] font-bold tracking-wider transition-colors ${
                      personnelFilter === f
                        ? 'bg-emerald-600 text-white'
                        : 'bg-[#151822] text-slate-400 hover:text-white border border-[#232838]'
                    }`}
                  >
                    {f.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {/* Responders Content List / Grid */}
            {isLoadingResponders && registeredResponders.length === 0 ? (
              <div className="p-12 text-center bg-[#0D0E13] rounded-sm border border-[#1E2232] space-y-3">
                <Icons.RefreshCw className="w-6 h-6 text-emerald-400 animate-spin mx-auto" />
                <div className="text-slate-300 font-bold text-sm">FETCHING FIELD PERSONNEL RECORDS...</div>
                <p className="text-slate-500 text-xs font-sans">Connecting to FastAPI responder registry...</p>
              </div>
            ) : registeredResponders.length === 0 ? (
              /* HONEST EMPTY STATE - STRICTLY NO FAKE/DEMO OFFICERS */
              <div className="p-12 text-center bg-[#0D0E13] rounded-sm border border-[#1E2232] space-y-4">
                <div className="w-12 h-12 rounded-full bg-slate-800/50 border border-slate-700/50 flex items-center justify-center mx-auto text-slate-400">
                  <Icons.Users className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h2 className="text-white font-bold text-sm tracking-wider uppercase">NO RESPONDERS REGISTERED</h2>
                  <p className="text-slate-400 text-xs max-w-md mx-auto font-sans leading-relaxed">
                    No field officers are currently registered in the database. Click below to add your first responder.
                  </p>
                </div>
                <div className="pt-2">
                  <button
                    onClick={() => {
                      setAddOfficerForm({ name: '', id: '', phone_number: '', role: 'Police Officer', unit: '' });
                      setAddOfficerError(null);
                      setShowAddOfficerModal(true);
                    }}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-sm text-xs transition-colors inline-flex items-center gap-2 shadow-md shadow-emerald-600/20 uppercase"
                  >
                    <Icons.Plus className="w-4 h-4" />
                    <span>ADD OFFICER</span>
                  </button>
                </div>
              </div>
            ) : (
              /* REAL REGISTERED OFFICERS GRID */
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {registeredResponders
                  .filter((officer) => {
                    if (personnelSearch.trim()) {
                      const q = personnelSearch.toLowerCase();
                      const matchName = (officer.name || '').toLowerCase().includes(q);
                      const matchId = (officer.id || '').toLowerCase().includes(q);
                      const matchRole = (officer.role || '').toLowerCase().includes(q);
                      const matchUnit = (officer.unit || '').toLowerCase().includes(q);
                      if (!matchName && !matchId && !matchRole && !matchUnit) return false;
                    }
                    const isOffDuty = (officer.status || '').toLowerCase() === 'offline' || !officer.status;
                    const isLive = (officer.live_state || '').toLowerCase() === 'live' && !isOffDuty;
                    if (personnelFilter === 'LIVE') return isLive;
                    if (personnelFilter === 'ON_DUTY') return !isOffDuty;
                    if (personnelFilter === 'OFF_DUTY') return isOffDuty;
                    return true;
                  })
                  .map((officer) => {
                    const isOffDuty = (officer.status || '').toLowerCase() === 'offline' || !officer.status;
                    const liveState = (officer.live_state || '').toLowerCase();
                    const isLive = liveState === 'live' && !isOffDuty;
                    const isStale = liveState === 'stale' && !isOffDuty;
                    const hasLocation = officer.latitude != null && officer.longitude != null;
                    const maskedPhone = maskPhoneNumber(officer.phone_number || officer.phone);
                    const lastSeenStr = formatTimeAgo(officer.last_seen_at || officer.location?.last_seen_at);
                    const accuracyMeters = officer.accuracy_meters != null 
                      ? officer.accuracy_meters 
                      : (officer.location?.accuracy_meters || null);

                    return (
                      <div
                        key={officer.id}
                        className={`bg-[#0D0E13] border rounded-sm p-4 space-y-4 flex flex-col justify-between transition-all ${
                          isLive
                            ? 'border-emerald-500/40 hover:border-emerald-500'
                            : 'border-[#1E2232] hover:border-[#2B3248]'
                        }`}
                      >
                        {/* Header: Officer Identity */}
                        <div className="space-y-2">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="text-white font-bold text-sm tracking-wide flex items-center gap-2">
                                <span>{officer.name || 'Unnamed Officer'}</span>
                              </div>
                              <div className="text-[11px] text-blue-400 font-mono mt-0.5 flex items-center gap-1.5">
                                <span className="px-1.5 py-0.2 bg-blue-500/10 border border-blue-500/20 rounded-sm font-bold">
                                  {officer.id}
                                </span>
                                <span className="text-slate-400">{officer.role || 'Police Officer'}</span>
                                {officer.unit && <span className="text-slate-500">• {officer.unit}</span>}
                              </div>
                            </div>

                            <button
                              onClick={() => handleDeleteOfficer(officer.id, officer.name)}
                              disabled={personnelDeletingId === officer.id}
                              className="text-slate-600 hover:text-rose-400 p-1 transition-colors"
                              title="Delete officer record"
                            >
                              <Icons.Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          {/* Contact */}
                          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                            <Icons.Phone className="w-3.5 h-3.5 text-slate-500" />
                            <span className="text-slate-300 font-semibold">{maskedPhone}</span>
                          </div>
                        </div>

                        {/* Status Badges & Telemetry */}
                        <div className="bg-[#11131A] p-3 rounded-sm border border-[#1E2232] space-y-2.5">
                          <div className="flex flex-wrap items-center gap-2">
                            {/* Duty Status Badge */}
                            <span className={`px-2 py-0.5 rounded-sm text-[10px] font-bold flex items-center gap-1 border ${
                              !isOffDuty
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                : 'bg-slate-800/40 border-slate-700/40 text-slate-400'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${!isOffDuty ? 'bg-emerald-400' : 'bg-slate-500'}`}></span>
                              <span>{!isOffDuty ? 'ON DUTY' : 'OFF DUTY'}</span>
                            </span>

                            {/* Location Status Badge */}
                            <span className={`px-2 py-0.5 rounded-sm text-[10px] font-bold flex items-center gap-1 border ${
                              isLive
                                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                                : isStale
                                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                                : isOffDuty
                                ? 'bg-slate-800/40 border-slate-700/40 text-slate-400'
                                : 'bg-slate-800/40 border-slate-700/40 text-slate-400'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full ${
                                isLive ? 'bg-emerald-400 animate-pulse' : isStale ? 'bg-amber-400' : 'bg-slate-500'
                              }`}></span>
                              <span>
                                {isLive
                                  ? 'LOCATION LIVE'
                                  : isStale
                                  ? 'STALE'
                                  : isOffDuty
                                  ? 'OFF DUTY'
                                  : hasLocation
                                  ? 'IDLE'
                                  : 'NO LOCATION'}
                              </span>
                            </span>
                          </div>

                          {/* Live Telemetry Info */}
                          <div className="space-y-1 text-[11px] text-slate-400 font-mono pt-1">
                            <div className="flex items-center justify-between">
                              <span className="text-slate-500">Last update:</span>
                              <span className="text-slate-200">{officer.last_seen_at ? lastSeenStr : 'No GPS telemetry received'}</span>
                            </div>
                            {accuracyMeters != null && (
                              <div className="flex items-center justify-between">
                                <span className="text-slate-500">Accuracy:</span>
                                <span className="text-emerald-400 font-bold">± {Number(accuracyMeters).toFixed(1)} m</span>
                              </div>
                            )}
                            {hasLocation && (
                              <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5 border-t border-[#1E2232]/60">
                                <span>Coordinates:</span>
                                <span className="text-slate-300">
                                  {Number(officer.latitude).toFixed(4)}°, {Number(officer.longitude).toFixed(4)}°
                                </span>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2 pt-1">
                          <button
                            onClick={() => handleOpenSendDutyLinkModal(officer)}
                            className="flex-1 py-2 bg-[#151822] hover:bg-[#1F2434] text-emerald-400 hover:text-emerald-300 border border-emerald-500/40 hover:border-emerald-500 rounded-sm font-bold text-xs flex items-center justify-center gap-1.5 transition-colors uppercase tracking-wider"
                          >
                            <Icons.Smartphone className="w-3.5 h-3.5" />
                            <span>SEND DUTY LINK</span>
                          </button>

                          <button
                            onClick={() => {
                              setDutyToken(officer.id);
                              setView('duty');
                            }}
                            className="p-2 bg-[#151822] hover:bg-[#1F2434] text-slate-400 hover:text-white border border-[#232838] rounded-sm transition-colors"
                            title="Open Mobile Duty View for this Officer"
                          >
                            <Icons.ExternalLink className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        )}

        {/* VIEW: MOBILE RESPONDER DUTY PAGE (/responder/duty/:token) */}
        {view === 'duty' && (
          <div className="flex-1 overflow-y-auto bg-[#08090C] text-slate-200 p-4 sm:p-6 flex flex-col items-center">
            <div className="w-full max-w-lg space-y-5 font-mono">
              
              {/* Tactical Mobile Header */}
              <div className="bg-[#0D0E13] border border-[#1E2232] p-4 rounded-md flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-sm bg-emerald-600/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
                    <Icons.Shield className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                      <span>SENTINEL-X</span>
                      <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-1 py-0.2 rounded-sm">FIELD</span>
                    </div>
                    <div className="text-[10px] text-slate-400">FIELD OPERATIONS CONSOLE</div>
                  </div>
                </div>

                {/* Duty Pill */}
                <div className={`px-2.5 py-1 rounded-sm border text-[10px] font-bold tracking-wider flex items-center gap-1.5 ${
                  dutyIsActive
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                    : 'bg-slate-800/60 border-slate-700/60 text-slate-400'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${dutyIsActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`}></span>
                  <span>{dutyIsActive ? 'ON DUTY' : 'OFF DUTY'}</span>
                </div>
              </div>

              {/* Officer Profile Card */}
              <div className="bg-[#0D0E13] border border-[#1E2232] p-4 rounded-md space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                  <span className="text-[10px] text-slate-500 uppercase font-bold tracking-wider">OFFICER PROFILE</span>
                  <span className="text-[10px] text-blue-400 font-bold">{dutyOfficer?.id || dutyToken}</span>
                </div>

                <div className="space-y-1">
                  <div className="text-base font-bold text-white">{dutyOfficer?.name || `Officer ${dutyToken}`}</div>
                  <div className="text-xs text-slate-400 flex items-center gap-2">
                    <span>{dutyOfficer?.role || 'Police Officer'}</span>
                    {dutyOfficer?.unit && <span className="text-slate-500">• {dutyOfficer.unit}</span>}
                  </div>
                  <div className="text-[11px] text-slate-400 pt-1 flex items-center gap-1.5">
                    <Icons.Phone className="w-3 h-3 text-slate-500" />
                    <span>{maskPhoneNumber(dutyOfficer?.phone_number || dutyOfficer?.phone)}</span>
                  </div>
                </div>
              </div>

              {/* LOGIN GATE -- shown until a real username/password login
                  succeeds. No duty controls are reachable before this. */}
              {!dutySessionToken ? (
                <div className="bg-[#0D0E13] border border-[#1E2232] p-5 rounded-md space-y-4">
                  <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                    <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                      <Icons.Shield className="w-4 h-4 text-emerald-400" />
                      <span>OFFICER LOGIN</span>
                    </span>
                  </div>

                  <form onSubmit={handleDutyLogin} className="space-y-3">
                    {dutyLoginError && (
                      <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-sm text-rose-300 text-xs flex items-center gap-2 font-sans">
                        <Icons.AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                        <span>{dutyLoginError}</span>
                      </div>
                    )}
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Username</label>
                      <input
                        type="text"
                        required
                        autoComplete="username"
                        value={dutyLoginForm.username}
                        onChange={(e) => setDutyLoginForm(f => ({ ...f, username: e.target.value }))}
                        placeholder="e.g. rahul.kumar"
                        className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2.5 text-white font-mono text-sm focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Password</label>
                      <input
                        type="password"
                        required
                        autoComplete="current-password"
                        value={dutyLoginForm.password}
                        onChange={(e) => setDutyLoginForm(f => ({ ...f, password: e.target.value }))}
                        placeholder="••••••••"
                        className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2.5 text-white font-mono text-sm focus:outline-none"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={dutyLoginSubmitting}
                      className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 active:scale-[0.98] text-white font-bold text-sm rounded-md flex items-center justify-center gap-2 transition-all shadow-lg shadow-emerald-600/30 uppercase tracking-wider"
                    >
                      {dutyLoginSubmitting ? (
                        <>
                          <Icons.RefreshCw className="w-4 h-4 animate-spin" />
                          <span>LOGGING IN...</span>
                        </>
                      ) : (
                        <span>LOG IN</span>
                      )}
                    </button>
                  </form>
                </div>
              ) : (
              <div className="bg-[#0D0E13] border border-[#1E2232] p-5 rounded-md space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                  <span className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                    <Icons.Radio className="w-4 h-4 text-emerald-400" />
                    <span>LOCATION STATUS</span>
                  </span>

                  {dutyLocationStatus === 'live' && (
                    <span className="text-emerald-400 font-bold text-[11px] flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                      <span>BROADCASTING</span>
                    </span>
                  )}
                </div>

                {/* Main Status Display */}
                <div className="p-4 bg-[#11131A] border border-[#1E2232] rounded-sm space-y-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${
                      dutyLocationStatus === 'live'
                        ? 'bg-emerald-400 animate-pulse'
                        : dutyLocationStatus === 'waiting'
                        ? 'bg-amber-400 animate-pulse'
                        : dutyLocationStatus === 'permission_denied' || dutyLocationStatus === 'unavailable' || dutyLocationStatus === 'error'
                        ? 'bg-rose-500'
                        : 'bg-slate-500'
                    }`}></span>
                    <span className={`text-sm font-bold tracking-wider uppercase ${
                      dutyLocationStatus === 'live'
                        ? 'text-emerald-400'
                        : dutyLocationStatus === 'waiting'
                        ? 'text-amber-400'
                        : dutyLocationStatus === 'permission_denied' || dutyLocationStatus === 'unavailable' || dutyLocationStatus === 'error'
                        ? 'text-rose-400'
                        : 'text-slate-400'
                    }`}>
                      {dutyLocationStatus === 'live'
                        ? 'LOCATION LIVE'
                        : dutyLocationStatus === 'waiting'
                        ? 'WAITING FOR GPS...'
                        : dutyLocationStatus === 'permission_denied'
                        ? 'LOCATION PERMISSION DENIED'
                        : dutyLocationStatus === 'unavailable'
                        ? 'LOCATION UNAVAILABLE'
                        : 'NOT SHARING'}
                    </span>
                  </div>

                  {/* Telemetry Metrics when LIVE */}
                  {dutyLocationStatus === 'live' && (
                    <div className="grid grid-cols-2 gap-2 pt-2 text-left text-xs">
                      <div className="bg-[#151822] p-2.5 rounded-sm border border-[#232838]">
                        <div className="text-[10px] text-slate-500 uppercase">Accuracy</div>
                        <div className="text-sm font-bold text-emerald-400 mt-0.5">
                          {dutyGpsData.accuracy_meters != null ? `± ${Number(dutyGpsData.accuracy_meters).toFixed(1)} m` : '± 8 m'}
                        </div>
                      </div>
                      <div className="bg-[#151822] p-2.5 rounded-sm border border-[#232838]">
                        <div className="text-[10px] text-slate-500 uppercase">Last Update</div>
                        <div className="text-sm font-bold text-white mt-0.5">
                          {dutySecondsSinceUpdate} sec ago
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Error explanations */}
                  {dutyLocationStatus === 'permission_denied' && (
                    <div className="text-left text-xs text-rose-300 bg-rose-500/10 border border-rose-500/30 p-3 rounded-sm space-y-1 font-sans">
                      <div className="font-bold font-mono text-rose-400">LOCATION PERMISSION REQUIRED</div>
                      <p>Please enable location permissions for this website in your Android Chrome browser settings to stream GPS coordinates.</p>
                    </div>
                  )}

                  {dutyLocationStatus === 'unavailable' && (
                    <div className="text-left text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 p-3 rounded-sm space-y-1 font-sans">
                      <div className="font-bold font-mono text-amber-400">GPS HARDWARE LOCK PENDING</div>
                      <p>Waiting for device GPS signal. Ensure Android Location toggle is ON and you are in an area with satellite visibility.</p>
                    </div>
                  )}
                </div>

                {/* Large Primary Action Button */}
                <div className="pt-2">
                  {!dutyIsActive ? (
                    <button
                      onClick={handleStartDuty}
                      className="w-full py-4 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white font-bold text-sm sm:text-base rounded-md flex items-center justify-center gap-2.5 transition-all shadow-lg shadow-emerald-600/30 uppercase tracking-wider"
                    >
                      <Icons.Play className="w-5 h-5 fill-current" />
                      <span>START DUTY</span>
                    </button>
                  ) : (
                    <button
                      onClick={handleStopDuty}
                      className="w-full py-4 bg-rose-600 hover:bg-rose-500 active:scale-[0.98] text-white font-bold text-sm sm:text-base rounded-md flex items-center justify-center gap-2.5 transition-all shadow-lg shadow-rose-600/30 uppercase tracking-wider"
                    >
                      <Icons.X className="w-5 h-5 stroke-[2.5]" />
                      <span>STOP DUTY</span>
                    </button>
                  )}
                </div>
              </div>
              )}

              {/* FEATURE 13: FIELD ASSISTANT (Deterministic Operational Helper) */}
              <div className="bg-[#0D0E13] border border-[#1E2232] p-4 rounded-md space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                  <div className="flex items-center gap-2 text-white font-bold text-xs uppercase tracking-wider">
                    <Icons.Bot className="w-4 h-4 text-blue-400" />
                    <span>FIELD ASSISTANT</span>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">OPERATIONAL SUPPORT</span>
                </div>

                {/* Quick Action Chips */}
                <div className="flex flex-wrap gap-1.5 text-[11px]">
                  {[
                    'How do I start duty?',
                    'How do I stop location?',
                    'Is my location live?',
                    'What is my duty status?',
                    'Why is location unavailable?'
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => handleSendFieldAssistantMessage(q)}
                      className="px-2.5 py-1 bg-[#151822] hover:bg-[#1F2434] text-slate-300 hover:text-white border border-[#232838] rounded-sm transition-colors text-left font-sans"
                    >
                      {q}
                    </button>
                  ))}
                </div>

                {/* Messages Container */}
                <div className="space-y-2 max-h-48 overflow-y-auto p-2.5 bg-[#08090C] rounded-sm border border-[#1E2232] text-xs font-sans">
                  {dutyAssistantMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      className={`p-2.5 rounded-sm whitespace-pre-wrap leading-relaxed ${
                        msg.sender === 'user'
                          ? 'bg-blue-600/20 text-blue-200 border border-blue-500/30 ml-6 text-right'
                          : 'bg-[#11131A] text-slate-200 border border-[#1E2232] mr-4 text-left font-mono text-[11px]'
                      }`}
                    >
                      {msg.text}
                    </div>
                  ))}
                </div>

                {/* Input Area */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendFieldAssistantMessage();
                  }}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    value={dutyAssistantInput}
                    onChange={(e) => setDutyAssistantInput(e.target.value)}
                    placeholder="Ask operational question..."
                    className="flex-1 bg-[#151822] border border-[#232838] focus:border-blue-500 rounded-sm px-3 py-1.5 text-white font-sans text-xs focus:outline-none placeholder:text-slate-600"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-sm text-xs transition-colors flex items-center gap-1"
                  >
                    <Icons.Send className="w-3.5 h-3.5" />
                    <span>Ask</span>
                  </button>
                </form>
              </div>

              {/* Navigation Back / Console Switch Link */}
              <div className="text-center pt-2 pb-4">
                <button
                  onClick={() => setView('personnel')}
                  className="text-xs text-slate-500 hover:text-slate-300 font-mono transition-colors underline underline-offset-4"
                >
                  ← Return to Desktop Command Console (Personnel Workspace)
                </button>
              </div>

            </div>
          </div>
        )}

        {/* VIEW: RESPONDER LIVE GPS TRACKER */}
        {view === 'tracker' && (
          <div className="flex-1 p-4 lg:p-8 max-w-6xl mx-auto w-full space-y-6 overflow-y-auto font-mono text-xs">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#1E2232] gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Icons.Radio className="w-5 h-5 text-emerald-400" />
                  <h1 className="text-lg font-bold text-white uppercase">LIVE RESPONDER MAP</h1>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Real-time positions of on-duty responders, reported from each officer's own phone during their duty session. Read-only.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setTrackerAutoRefresh((v) => !v)}
                  className={`px-2.5 py-1 rounded-sm border text-[10px] font-bold tracking-wider uppercase transition-colors ${
                    trackerAutoRefresh
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-[#151822] border-[#232838] text-slate-400'
                  }`}
                >
                  ● {trackerAutoRefresh ? 'AUTO-REFRESH ON' : 'AUTO-REFRESH OFF'}
                </button>
                <button
                  onClick={refreshTrackerLocations}
                  className="px-3 py-1 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-blue-400 border border-blue-500/40 font-bold flex items-center gap-1.5 transition-colors"
                >
                  <Icons.RefreshCw className="w-3.5 h-3.5" />
                  <span>REFRESH NOW</span>
                </button>
              </div>
            </div>

            {/* Roster summary strip */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 bg-[#0D0E13] border border-[#1E2232] rounded-sm">
                <div className="text-[10px] text-slate-500 uppercase">Total Responders</div>
                <div className="text-xl font-bold text-white mt-0.5">{registeredResponders.length}</div>
              </div>
              <div className="p-3 bg-[#0D0E13] border border-[#1E2232] rounded-sm">
                <div className="text-[10px] text-slate-500 uppercase">Live Now</div>
                <div className="text-xl font-bold text-emerald-400 mt-0.5">
                  {registeredResponders.filter(r => (r.live_state || '').toLowerCase() === 'live' && (r.status || '').toLowerCase() !== 'offline').length}
                </div>
              </div>
              <div className="p-3 bg-[#0D0E13] border border-[#1E2232] rounded-sm">
                <div className="text-[10px] text-slate-500 uppercase">On Map (Has Location)</div>
                <div className="text-xl font-bold text-blue-400 mt-0.5">
                  {registeredResponders.filter(r => r.latitude != null && r.longitude != null).length}
                </div>
              </div>
            </div>

            {/* Live map */}
            <div className="bg-[#0D0E13] border border-[#1E2232] rounded-sm overflow-hidden" style={{ height: '480px' }}>
              <div ref={trackerMapContainerRef} className="w-full h-full" />
            </div>

            {/* Route-to-incident status, shown only once a responder with an
                assigned incident is selected */}
            {selectedTrackerResponderId && (
              <div className="flex items-center gap-2 text-[11px]">
                {trackerRouteLoading && (
                  <span className="text-blue-400 flex items-center gap-1.5">
                    <Icons.RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    Calculating route to assigned incident...
                  </span>
                )}
                {!trackerRouteLoading && trackerAssignedIncident && !trackerRouteError && (
                  <span className="text-emerald-400 font-bold">
                    ● Road route shown to: {trackerAssignedIncident.label}
                  </span>
                )}
                {!trackerRouteLoading && trackerRouteError && (
                  <span className="text-amber-400">{trackerRouteError}</span>
                )}
                {!trackerRouteLoading && !trackerAssignedIncident && (
                  <span className="text-slate-500">No recent dispatch found for this responder -- no route to show.</span>
                )}
              </div>
            )}

            {registeredResponders.filter(r => r.latitude != null && r.longitude != null).length === 0 && (
              <div className="p-8 text-center bg-[#11131A] rounded-sm border border-[#1E2232] space-y-2">
                <Icons.MapPin className="w-8 h-8 text-slate-600 mx-auto" />
                <div className="text-slate-300 font-bold">No responder locations yet</div>
                <p className="text-slate-500 text-xs max-w-md mx-auto font-sans">
                  Locations appear here once an officer logs into their duty page and taps "Start Duty" on their own phone.
                </p>
              </div>
            )}

            {/* Roster list, click to focus on map */}
            <div className="bg-[#0D0E13] border border-[#1E2232] rounded-sm">
              <div className="px-4 py-2.5 border-b border-[#1E2232] text-[11px] font-bold text-white uppercase">
                Responder Roster
              </div>
              <div className="divide-y divide-[#1E2232] max-h-64 overflow-y-auto">
                {registeredResponders.map((r) => {
                  const isLive = (r.live_state || '').toLowerCase() === 'live' && (r.status || '').toLowerCase() !== 'offline';
                  const hasLocation = r.latitude != null && r.longitude != null;
                  return (
                    <button
                      key={r.id}
                      onClick={() => {
                        setSelectedTrackerResponderId(r.id);
                        if (hasLocation && trackerMapInstanceRef.current) {
                          trackerMapInstanceRef.current.setView([r.latitude, r.longitude], 15);
                        }
                      }}
                      disabled={!hasLocation}
                      className={`w-full text-left px-4 py-2.5 flex items-center justify-between gap-3 transition-colors ${
                        hasLocation ? 'hover:bg-[#151822] cursor-pointer' : 'opacity-50 cursor-default'
                      } ${selectedTrackerResponderId === r.id ? 'bg-[#151822]' : ''}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-400' : 'bg-slate-600'}`}></span>
                        <span className="text-white font-bold">{r.name || r.id}</span>
                        <span className="text-slate-500">({r.unit || r.role || 'Officer'})</span>
                      </div>
                      <span className="text-[10px] text-slate-500">
                        {hasLocation ? `${Number(r.latitude).toFixed(4)}°, ${Number(r.longitude).toFixed(4)}°` : 'No location reported'}
                      </span>
                    </button>
                  );
                })}
                {registeredResponders.length === 0 && (
                  <div className="px-4 py-6 text-center text-slate-500">No responders registered yet.</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* VIEW 5: FULL-PAGE SETTINGS / ADMINISTRATION WORKSPACE */}
        {view === 'settings' && (
          <div className="flex-1 flex flex-col overflow-hidden bg-[#08090C]">
            
            {/* Settings Workspace Header */}
            <div className="h-14 bg-[#0D0E13] border-b border-[#1E2232] px-4 lg:px-6 flex items-center justify-between shrink-0 font-mono text-xs">
              <div className="flex items-center gap-3">
                <button
                  onClick={closeSettings}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-sm bg-[#151822] hover:bg-[#1F2434] border border-[#232838] hover:border-blue-500/50 text-slate-200 hover:text-white transition-all group"
                  title={`Return to ${previousView.toUpperCase()}`}
                >
                  <Icons.CornerDownLeft className="w-3.5 h-3.5 text-blue-400 group-hover:-translate-x-0.5 transition-transform" />
                  <span className="font-bold tracking-wide">BACK TO COMMAND</span>
                  <span className="text-[10px] text-slate-500 font-normal hidden sm:inline">({previousView.toUpperCase()})</span>
                </button>

                <div className="h-4 w-[1px] bg-[#1E2232]"></div>

                <div className="flex items-center gap-2">
                  <Icons.Settings className="w-4 h-4 text-blue-400" />
                  <span className="font-bold text-white uppercase tracking-wider">SETTINGS / SYSTEM CONFIGURATION</span>
                </div>
              </div>

              <div className="flex items-center gap-3 text-[11px]">
                <div className="hidden sm:flex items-center gap-2 text-slate-400">
                  <span>SYSTEM STATUS:</span>
                  <div className="flex items-center gap-1.5 font-bold">
                    <span className={`w-2 h-2 rounded-full ${apiHealth.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`}></span>
                    <span className={apiHealth.connected ? 'text-emerald-400' : 'text-rose-400'}>
                      {apiHealth.connected ? 'ONLINE (FASTAPI)' : simulatedEngineMode ? 'SIMULATED' : 'OFFLINE'}
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => {
                    checkBackendHealth();
                    fetchSmsConfig();
                    fetchSmsStatus();
                    fetchYoloHealth();
                    showToast('System telemetry refreshed.');
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm bg-[#151822] hover:bg-[#1B202E] text-slate-300 hover:text-white border border-[#232838] transition-colors"
                  title="Refresh Telemetry"
                >
                  <Icons.RefreshCw className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">REFRESH</span>
                </button>
              </div>
            </div>

            {/* Settings Workspace Body (Sidebar Nav + Main Content) */}
            <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
              
              {/* LEFT NAVIGATION SIDEBAR */}
              <div className="w-full md:w-64 lg:w-72 bg-[#0D0E13] border-r border-[#1E2232] flex flex-col shrink-0 overflow-y-auto font-mono text-xs p-4 space-y-6">
                
                {/* GROUP 1: SYSTEM */}
                <div className="space-y-1.5">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-2.5 pb-1">
                    SYSTEM
                  </div>
                  
                  <button
                    onClick={() => setSettingsTab('overview')}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-sm transition-all text-left ${
                      settingsTab === 'overview'
                        ? 'bg-[#151822] text-white font-bold border-l-2 border-blue-500 border-y border-r border-[#232838]'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icons.Activity className="w-4 h-4 text-blue-400" />
                      <span>Overview</span>
                    </div>
                    <span className={`w-1.5 h-1.5 rounded-full ${apiHealth.connected ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                  </button>

                  <button
                    onClick={() => setSettingsTab('backend')}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-sm transition-all text-left ${
                      settingsTab === 'backend'
                        ? 'bg-[#151822] text-white font-bold border-l-2 border-blue-500 border-y border-r border-[#232838]'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icons.Server className="w-4 h-4 text-indigo-400" />
                      <span>API / Backend</span>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono">:8000</span>
                  </button>
                </div>

                {/* GROUP 2: COMMUNICATIONS */}
                <div className="space-y-1.5">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-2.5 pb-1">
                    COMMUNICATIONS
                  </div>

                  <button
                    onClick={() => setSettingsTab('sms')}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-sm transition-all text-left ${
                      settingsTab === 'sms'
                        ? 'bg-[#151822] text-white font-bold border-l-2 border-blue-500 border-y border-r border-[#232838]'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icons.Radio className="w-4 h-4 text-emerald-400" />
                      <span>SMS Gateway</span>
                    </div>
                    <div className={`px-1.5 py-0.2 rounded-sm text-[9px] border font-bold ${smsBadgeClassFor(smsConnectionState)}`}>
                      {smsLabelFor(smsConnectionState)}
                    </div>
                  </button>
                </div>

                {/* GROUP 3: APPLICATION */}
                <div className="space-y-1.5">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-2.5 pb-1">
                    APPLICATION
                  </div>

                  <button
                    onClick={() => setSettingsTab('interface')}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-sm transition-all text-left ${
                      settingsTab === 'interface'
                        ? 'bg-[#151822] text-white font-bold border-l-2 border-blue-500 border-y border-r border-[#232838]'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icons.Map className="w-4 h-4 text-amber-400" />
                      <span>Interface &amp; Map</span>
                    </div>
                  </button>

                  <button
                    onClick={() => setSettingsTab('diagnostics')}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-sm transition-all text-left ${
                      settingsTab === 'diagnostics'
                        ? 'bg-[#151822] text-white font-bold border-l-2 border-blue-500 border-y border-r border-[#232838]'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icons.Zap className="w-4 h-4 text-cyan-400" />
                      <span>Diagnostics</span>
                    </div>
                    <span className="text-[10px] text-emerald-400 font-mono">SOC</span>
                  </button>
                </div>

                {/* Sidebar Footer Info */}
                <div className="mt-auto pt-6 border-t border-[#1E2232] text-[10px] text-slate-500 space-y-1">
                  <div>SENTINEL-X SOC v2.4.0</div>
                  <div>Security Operations Console</div>
                </div>
              </div>

              {/* MAIN CONTENT AREA */}
              <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 bg-[#08090C] font-mono text-xs space-y-6">
                
                {/* SUB-VIEW 1: OVERVIEW */}
                {settingsTab === 'overview' && (
                  <div className="max-w-5xl space-y-6">
                    
                    {/* Section Header */}
                    <div>
                      <h2 className="text-base font-bold text-white uppercase flex items-center gap-2">
                        <Icons.Activity className="w-4 h-4 text-blue-400" />
                        <span>System Overview &amp; Operational Health</span>
                      </h2>
                      <p className="text-slate-400 text-xs mt-1 font-sans">
                        Aggregated diagnostics across FastAPI backend, deep learning inference pipelines, vision models, and communications modem.
                      </p>
                    </div>

                    {/* Top Operational Metrics Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      
                      {/* Metric 1: Backend API */}
                      <div className="p-4 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-2">
                        <div className="flex items-center justify-between text-slate-400 text-[11px]">
                          <span>BACKEND API</span>
                          <span className={`w-2 h-2 rounded-full ${apiHealth.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`}></span>
                        </div>
                        <div className={`text-lg font-bold ${apiHealth.connected ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {apiHealth.connected ? 'ONLINE' : simulatedEngineMode ? 'SIMULATED' : 'OFFLINE'}
                        </div>
                        <div className="text-[10px] text-slate-500 flex justify-between">
                          <span>Port 8000</span>
                          <span>{apiHealth.latencyMs ? `${apiHealth.latencyMs}ms` : 'Checked'}</span>
                        </div>
                      </div>

                      {/* Metric 2: Anomaly Pipeline */}
                      <div className="p-4 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-2">
                        <div className="flex items-center justify-between text-slate-400 text-[11px]">
                          <span>ANOMALY PIPELINE</span>
                          <span className="w-2 h-2 rounded-full bg-blue-400"></span>
                        </div>
                        <div className="text-lg font-bold text-blue-400">
                          2-STAGE
                        </div>
                        <div className="text-[10px] text-slate-500 flex justify-between">
                          <span>I3D + Stage1 + Stage2</span>
                          <span className="text-emerald-400">Loaded</span>
                        </div>
                      </div>

                      {/* Metric 3: Vision YOLO */}
                      <div className="p-4 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-2">
                        <div className="flex items-center justify-between text-slate-400 text-[11px]">
                          <span>VISION / YOLO</span>
                          <span className={`w-2 h-2 rounded-full ${yoloHealth.yolo_ready ? 'bg-emerald-400' : 'bg-slate-500'}`}></span>
                        </div>
                        <div className="text-lg font-bold text-white">
                          {yoloHealth.yolo_ready ? 'INITIALIZED' : 'STANDBY'}
                        </div>
                        <div className="text-[10px] text-slate-500 flex justify-between">
                          <span>DeepSORT Tracker</span>
                          <span>Kalman</span>
                        </div>
                      </div>

                      {/* Metric 4: SMS Gateway */}
                      <div className="p-4 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-2">
                        <div className="flex items-center justify-between text-slate-400 text-[11px]">
                          <span>SMS GATEWAY</span>
                          <span className={`w-2 h-2 rounded-full ${smsDotClassFor(smsConnectionState)}`}></span>
                        </div>
                        <div className={`text-lg font-bold ${
                          smsConnectionState === 'connected' ? 'text-emerald-400' : smsConnectionState === 'unreachable' ? 'text-rose-400' : 'text-slate-300'
                        }`}>
                          {smsLabelFor(smsConnectionState)}
                        </div>
                        <div className="text-[10px] text-slate-500 flex justify-between">
                          <span>{smsConfig.enabled ? 'Modem Enabled' : 'Disabled'}</span>
                          <span>{smsConfig.password_configured ? 'Auth Set' : 'No Auth'}</span>
                        </div>
                      </div>

                    </div>

                    {/* Detailed System Specifications Breakdown */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      
                      {/* Checkpoint & Architecture Manifest */}
                      <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                        <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                          <span className="font-bold text-white uppercase flex items-center gap-2">
                            <Icons.Cpu className="w-4 h-4 text-blue-400" />
                            <span>Inference Checkpoints &amp; Weights</span>
                          </span>
                          <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-sm border border-blue-500/20">
                            VRAM RESIDENT
                          </span>
                        </div>

                        <div className="space-y-3 text-[11px]">
                          <div className="flex justify-between items-start pb-2 border-b border-[#161924]">
                            <div>
                              <div className="text-white font-bold">I3D Backbone Feature Extractor</div>
                              <div className="text-slate-400 text-[10px]">Inflated 3D Convolutional Network (1024-dim features)</div>
                            </div>
                            <span className="text-emerald-400 font-mono">model_i3d.pt</span>
                          </div>

                          <div className="flex justify-between items-start pb-2 border-b border-[#161924]">
                            <div>
                              <div className="text-white font-bold">Stage 1 Binary Anomaly Classifier</div>
                              <div className="text-slate-400 text-[10px]">Detects anomalous video segments via temporal attention</div>
                            </div>
                            <span className="text-emerald-400 font-mono">stage1_checkpoint.pt</span>
                          </div>

                          <div className="flex justify-between items-start pb-2 border-b border-[#161924]">
                            <div>
                              <div className="text-white font-bold">Stage 2 Action Classifier (V2)</div>
                              <div className="text-slate-400 text-[10px]">13-Class fine-grained tactical action discriminator</div>
                            </div>
                            <span className="text-emerald-400 font-mono">stage2_v2_checkpoint.pt</span>
                          </div>

                          <div className="flex justify-between items-start">
                            <div>
                              <div className="text-white font-bold">YOLOv8 Multi-Object Vision Layer</div>
                              <div className="text-slate-400 text-[10px]">Bounding box localization &amp; DeepSORT trajectory tracking</div>
                            </div>
                            <span className="text-indigo-400 font-mono">yolov8n.pt</span>
                          </div>
                        </div>
                      </div>

                      {/* Operational Telemetry & Active Environment */}
                      <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                        <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                          <span className="font-bold text-white uppercase flex items-center gap-2">
                            <Icons.Layers className="w-4 h-4 text-emerald-400" />
                            <span>Tactical Operational Environment</span>
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            NIPANI SECTOR
                          </span>
                        </div>

                        <div className="space-y-3 text-[11px]">
                          <div className="flex justify-between items-center pb-2 border-b border-[#161924]">
                            <span className="text-slate-400">Tactical Sector Center:</span>
                            <span className="text-white font-bold">Nipani City, Karnataka, India (16.4022° N, 74.3820° E)</span>
                          </div>
                          
                          <div className="flex justify-between items-center pb-2 border-b border-[#161924]">
                            <span className="text-slate-400">Map Tile Provider:</span>
                            <span className="text-blue-400 font-bold">CartoDB Voyager Raster XYZ Layer</span>
                          </div>

                          <div className="flex justify-between items-center pb-2 border-b border-[#161924]">
                            <span className="text-slate-400">Active Video Source:</span>
                            <span className="text-white font-bold truncate max-w-[200px]">{selectedSource.title}</span>
                          </div>

                          <div className="flex justify-between items-center pb-2 border-b border-[#161924]">
                            <span className="text-slate-400">Session Audit Entries:</span>
                            <span className="text-emerald-400 font-bold">{jobHistory.length} Scans Archived</span>
                          </div>

                          <div className="flex justify-between items-center">
                            <span className="text-slate-400">Automatic Trigger Status:</span>
                            <span className="text-blue-400 font-bold">HTML5 First-Play Event Guarded</span>
                          </div>
                        </div>
                      </div>

                    </div>

                    {/* Quick Action Bar */}
                    <div className="flex flex-wrap gap-3 pt-2">
                      <button
                        onClick={() => setSettingsTab('sms')}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-sm font-bold flex items-center gap-2 transition-colors"
                      >
                        <Icons.Radio className="w-4 h-4" />
                        <span>CONFIGURE SMS GATEWAY</span>
                      </button>
                      
                      <button
                        onClick={() => setSettingsTab('backend')}
                        className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] text-slate-200 hover:text-white border border-[#232838] rounded-sm font-bold flex items-center gap-2 transition-colors"
                      >
                        <Icons.Server className="w-4 h-4 text-indigo-400" />
                        <span>BACKEND ENDPOINTS</span>
                      </button>

                      <button
                        onClick={() => setSettingsTab('diagnostics')}
                        className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] text-cyan-400 hover:text-cyan-300 border border-cyan-500/40 rounded-sm font-bold flex items-center gap-2 transition-colors"
                      >
                        <Icons.Zap className="w-4 h-4" />
                        <span>RUN FULL DIAGNOSTICS</span>
                      </button>
                    </div>

                  </div>
                )}

                {/* SUB-VIEW 2: API / BACKEND */}
                {settingsTab === 'backend' && (
                  <div className="max-w-4xl space-y-6">
                    
                    <div>
                      <h2 className="text-base font-bold text-white uppercase flex items-center gap-2">
                        <Icons.Server className="w-4 h-4 text-indigo-400" />
                        <span>FastAPI Inference Server Configuration</span>
                      </h2>
                      <p className="text-slate-400 text-xs mt-1 font-sans">
                        Configure connection parameters, probe backend inference health, and adjust offline worker modes.
                      </p>
                    </div>

                    {/* Server Base URL Config */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">FastAPI Server Endpoint</h3>
                      
                      <div className="space-y-3">
                        <div>
                          <label className="text-slate-400 block mb-1.5 text-[11px]">Backend Base URL</label>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={backendUrl}
                              onChange={(e) => setBackendUrl(e.target.value)}
                              placeholder="http://localhost:8000"
                              className="flex-1 bg-[#151822] border border-[#232838] focus:border-blue-500 rounded-sm px-3 py-2 text-white font-mono focus:outline-none"
                            />
                            <button
                              onClick={() => {
                                checkBackendHealth();
                                showToast('Pinging FastAPI server...');
                              }}
                              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-sm transition-colors"
                            >
                              Save &amp; Ping
                            </button>
                            <button
                              onClick={() => {
                                setBackendUrl('http://localhost:8000');
                                showToast('Reset backend URL to default: http://localhost:8000');
                              }}
                              className="px-3 py-2 bg-[#151822] hover:bg-[#1B202E] text-slate-300 border border-[#232838] rounded-sm"
                              title="Reset to default port 8000"
                            >
                              Reset
                            </button>
                          </div>
                        </div>

                        {/* Live Ping Status Indicator */}
                        <div className="p-3 bg-[#11131A] rounded-sm border border-[#1E2232] flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
                          <div className="flex items-center gap-2">
                            <span className={`w-2 h-2 rounded-full ${apiHealth.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`}></span>
                            <span className="text-slate-300">
                              Status: <strong className={apiHealth.connected ? 'text-emerald-400' : 'text-rose-400'}>{apiHealth.connected ? 'CONNECTED (200 OK)' : 'OFFLINE / UNREACHABLE'}</strong>
                            </span>
                          </div>
                          <div className="text-slate-400 font-mono">
                            Endpoint: <span className="text-slate-200">{backendUrl}/api/health</span>
                          </div>
                        </div>

                        {/* Simulation Mode Toggle */}
                        <div className="pt-2">
                          <label className="flex items-center gap-2.5 text-slate-300 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={simulatedEngineMode}
                              onChange={(e) => setSimulatedEngineMode(e.target.checked)}
                              className="rounded-sm border-[#232838] bg-[#151822] text-blue-600 focus:ring-0"
                            />
                            <span className="font-bold">Enable Simulated Offline Inference Worker</span>
                          </label>
                          <p className="text-[11px] text-slate-500 mt-1 font-sans pl-6">
                            Allows testing UI components and mock job processing when the real FastAPI backend is not running.
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Backend Endpoint Manifest Table */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                        <Icons.Terminal className="w-4 h-4 text-blue-400" />
                        <span>Registered Backend Endpoint Manifest</span>
                      </h3>

                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-[11px]">
                          <thead>
                            <tr className="border-b border-[#1E2232] text-slate-500 uppercase text-[10px]">
                              <th className="pb-2">Method</th>
                              <th className="pb-2">Endpoint Route</th>
                              <th className="pb-2">Contract / Payload</th>
                              <th className="pb-2 text-right">Target Pipeline</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#161924] text-slate-300">
                            <tr>
                              <td className="py-2 font-bold text-emerald-400">GET</td>
                              <td className="py-2 text-white font-mono">/api/health</td>
                              <td className="py-2 text-slate-400">{"{ status, inference_ready }"}</td>
                              <td className="py-2 text-right text-blue-400">Health Probe</td>
                            </tr>
                            <tr>
                              <td className="py-2 font-bold text-blue-400">POST</td>
                              <td className="py-2 text-white font-mono">/api/v1/analysis</td>
                              <td className="py-2 text-slate-400">multipart/form-data (file: Video)</td>
                              <td className="py-2 text-right text-blue-400">Anomaly Classifier</td>
                            </tr>
                            <tr>
                              <td className="py-2 font-bold text-emerald-400">GET</td>
                              <td className="py-2 text-white font-mono">/api/v1/analysis/{"{job_id}"}</td>
                              <td className="py-2 text-slate-400">Job status &amp; temporal evidence</td>
                              <td className="py-2 text-right text-blue-400">Job Polling</td>
                            </tr>
                            <tr>
                              <td className="py-2 font-bold text-blue-400">POST</td>
                              <td className="py-2 text-white font-mono">/api/v1/yolo/detect</td>
                              <td className="py-2 text-slate-400">multipart/form-data (file, zones)</td>
                              <td className="py-2 text-right text-indigo-400">YOLOv8 Detection</td>
                            </tr>
                            <tr>
                              <td className="py-2 font-bold text-emerald-400">GET</td>
                              <td className="py-2 text-white font-mono">/api/v1/notifications/sms/config</td>
                              <td className="py-2 text-slate-400">{"{ enabled, url, username, password_configured }"}</td>
                              <td className="py-2 text-right text-emerald-400">SMS Gateway</td>
                            </tr>
                            <tr>
                              <td className="py-2 font-bold text-blue-400">POST</td>
                              <td className="py-2 text-white font-mono">/api/v1/notifications/sms/test-connection</td>
                              <td className="py-2 text-slate-400">Probes Android modem reachability</td>
                              <td className="py-2 text-right text-emerald-400">SMS Gateway</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>

                  </div>
                )}

                {/* SUB-VIEW 3: SMS GATEWAY */}
                {settingsTab === 'sms' && (
                  <div className="max-w-4xl space-y-6">
                    
                    <div>
                      <h2 className="text-base font-bold text-white uppercase flex items-center gap-2">
                        <Icons.Radio className="w-4 h-4 text-emerald-400" />
                        <span>SMS Gateway (Communications &amp; Incident Dispatch)</span>
                      </h2>
                      <p className="text-slate-400 text-xs mt-1 font-sans">
                        Isolated Android SMS modem integration. Probes physical modem connectivity and dispatches real carrier notifications.
                      </p>
                    </div>

                    {/* Live Truthful Connection Status Banner */}
                    <div className="p-4 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 font-bold text-white text-xs uppercase">
                          <Icons.Radio className="w-4 h-4 text-emerald-400" />
                          <span>MODEM CONNECTION STATUS</span>
                        </div>
                        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-sm border text-[10px] font-bold tracking-wider ${smsBadgeClassFor(smsConnectionState)}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${smsDotClassFor(smsConnectionState)}`}></span>
                          <span>{smsLabelFor(smsConnectionState)}</span>
                        </div>
                      </div>

                      {/* Status Detail & Truthful Feedback */}
                      <div className="p-3 bg-[#11131A] rounded-sm border border-[#1E2232] space-y-1 text-[11px]">
                        <div className="flex justify-between text-slate-400">
                          <span>Gateway Service State:</span>
                          <span className="text-slate-200 font-bold">{smsConfig.enabled ? 'ENABLED' : 'DISABLED'}</span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>Credentials Configured:</span>
                          <span className={smsConfig.password_configured ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold'}>
                            {smsConfig.password_configured ? 'YES (PASSWORD STORED)' : 'NO PASSWORD'}
                          </span>
                        </div>
                        {smsLastCheckedAt && (
                          <div className="flex justify-between text-slate-500 text-[10px] pt-1 border-t border-[#1E2232]">
                            <span>Last Reachability Probe:</span>
                            <span>{smsLastCheckedAt.toLocaleTimeString()}</span>
                          </div>
                        )}
                        {smsConnectionDetail && (
                          <div className="text-[11px] text-slate-300 font-mono pt-1">
                            Response: <span className="text-blue-400">{smsConnectionDetail}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Gateway Parameters Form */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">Gateway Configuration Parameters</h3>
                      
                      <div className="space-y-4">
                        {/* Enable Gateway Toggle */}
                        <label className="flex items-center gap-2.5 text-slate-200 cursor-pointer select-none">
                          <input
                            type="checkbox"
                            checked={smsConfig.enabled}
                            onChange={(e) => setSmsConfig(c => ({ ...c, enabled: e.target.checked }))}
                            className="rounded-sm border-[#232838] bg-[#151822] text-blue-600 focus:ring-0"
                          />
                          <span className="font-bold">Enable Android SMS Modem Gateway</span>
                        </label>

                        {/* Gateway URL */}
                        <div>
                          <label className="text-slate-400 block mb-1 text-[11px]">
                            Gateway Server URL <span className="text-slate-500">(Local Android HTTP endpoint)</span>
                          </label>
                          <input
                            type="text"
                            value={smsConfig.url}
                            onChange={(e) => setSmsConfig(c => ({ ...c, url: e.target.value }))}
                            placeholder="http://192.168.1.50:8080 or http://10.0.0.5:8080"
                            className="w-full bg-[#151822] border border-[#232838] focus:border-blue-500 rounded-sm px-3 py-2 text-white font-mono focus:outline-none"
                          />
                        </div>

                        {/* Username */}
                        <div>
                          <label className="text-slate-400 block mb-1 text-[11px]">
                            Gateway Username
                          </label>
                          <input
                            type="text"
                            value={smsConfig.username}
                            onChange={(e) => setSmsConfig(c => ({ ...c, username: e.target.value }))}
                            placeholder="sms"
                            className="w-full bg-[#151822] border border-[#232838] focus:border-blue-500 rounded-sm px-3 py-2 text-white font-mono focus:outline-none"
                          />
                        </div>

                        {/* Password */}
                        <div>
                          <label className="text-slate-400 block mb-1 text-[11px]">
                            Gateway Password
                            {smsConfig.password_configured && (
                              <span className="text-emerald-400 ml-2 font-normal">(Password is saved in backend. Leave blank to keep existing password.)</span>
                            )}
                          </label>
                          <input
                            type="password"
                            value={smsPasswordInput}
                            onChange={(e) => setSmsPasswordInput(e.target.value)}
                            placeholder={smsConfig.password_configured ? '•••••••• (Leave blank to keep existing)' : 'Enter modem password'}
                            autoComplete="new-password"
                            className="w-full bg-[#151822] border border-[#232838] focus:border-blue-500 rounded-sm px-3 py-2 text-white font-mono focus:outline-none"
                          />
                        </div>

                        {/* Actions Toolbar */}
                        <div className="flex flex-wrap gap-2 pt-2">
                          <button
                            onClick={handleSaveSmsConfig}
                            disabled={smsConfigSaving}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold rounded-sm transition-colors"
                          >
                            {smsConfigSaving ? 'Saving Configuration...' : 'Save Configuration'}
                          </button>
                          
                          <button
                            onClick={handleTestSmsConnection}
                            disabled={smsConnectionState === 'testing'}
                            className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] disabled:opacity-50 text-blue-400 border border-blue-500/40 font-bold rounded-sm transition-colors flex items-center gap-2"
                          >
                            <Icons.RefreshCw className={`w-3.5 h-3.5 ${smsConnectionState === 'testing' ? 'animate-spin' : ''}`} />
                            <span>{smsConnectionState === 'testing' ? 'Probing Gateway...' : 'Test Connection'}</span>
                          </button>

                          <button
                            onClick={() => {
                              fetchSmsConfig();
                              fetchSmsStatus();
                              showToast('Refreshed SMS configuration from backend.');
                            }}
                            className="px-3 py-2 bg-[#151822] hover:bg-[#1B202E] text-slate-400 hover:text-slate-200 border border-[#232838] rounded-sm"
                            title="Reload from backend"
                          >
                            Reload From Backend
                          </button>
                        </div>

                      </div>
                    </div>

                    {/* Test SMS Dispatch Card */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                        <span className="text-xs font-bold text-white uppercase flex items-center gap-2">
                          <Icons.Send className="w-4 h-4 text-blue-400" />
                          <span>Dispatch Real Test SMS</span>
                        </span>
                        <span className="text-[10px] text-slate-500">CARRIER TRANSMISSION</span>
                      </div>

                      <div className="space-y-3">
                        <div>
                          <label className="text-slate-400 block mb-1 text-[11px]">
                            Destination Mobile Number (E.164 format)
                          </label>
                          <div className="flex gap-2">
                            <input
                              type="text"
                              value={smsTestRecipient}
                              onChange={(e) => setSmsTestRecipient(e.target.value)}
                              placeholder="+919876543210 or +15551234567"
                              className="flex-1 bg-[#151822] border border-[#232838] focus:border-blue-500 rounded-sm px-3 py-2 text-white font-mono focus:outline-none"
                            />
                            <button
                              onClick={handleSendTestSms}
                              disabled={smsTestSmsState === 'sending' || !smsTestRecipient.trim()}
                              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold rounded-sm transition-colors flex items-center gap-1.5"
                            >
                              <Icons.Send className="w-3.5 h-3.5" />
                              <span>{smsTestSmsState === 'sending' ? 'Dispatching...' : 'Send Test SMS'}</span>
                            </button>
                          </div>
                        </div>

                        {/* Test SMS Outcome */}
                        {smsTestSmsState === 'sent' && (
                          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-sm text-emerald-400 text-xs flex items-center gap-2">
                            <Icons.CheckCircle className="w-4 h-4 shrink-0" />
                            <span>SMS DISPATCHED SUCCESSFULLY: {smsTestSmsDetail || 'Message received by Android gateway modem.'}</span>
                          </div>
                        )}

                        {smsTestSmsState === 'failed' && (
                          <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-sm text-rose-400 text-xs flex items-center gap-2">
                            <Icons.AlertTriangle className="w-4 h-4 shrink-0" />
                            <span>DISPATCH REJECTED: {smsTestSmsDetail || 'Failed to dispatch SMS through Android modem.'}</span>
                          </div>
                        )}
                      </div>
                    </div>

                  </div>
                )}

                {/* SUB-VIEW 4: INTERFACE & MAP */}
                {settingsTab === 'interface' && (
                  <div className="max-w-4xl space-y-6">
                    
                    <div>
                      <h2 className="text-base font-bold text-white uppercase flex items-center gap-2">
                        <Icons.Map className="w-4 h-4 text-amber-400" />
                        <span>Interface Preferences &amp; Geospatial Radar</span>
                      </h2>
                      <p className="text-slate-400 text-xs mt-1 font-sans">
                        Geospatial radar configuration, CartoDB tile layer parameters, and video workspace defaults.
                      </p>
                    </div>

                    {/* Map Provider Card */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                        <span className="text-xs font-bold text-white uppercase flex items-center gap-2">
                          <Icons.MapPin className="w-4 h-4 text-emerald-400" />
                          <span>Geospatial Radar Integration</span>
                        </span>
                        <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-sm border border-emerald-500/20">
                          VOYAGER RASTER ACTIVE
                        </span>
                      </div>

                      <div className="space-y-3 text-[11px]">
                        <div className="flex justify-between py-1.5 border-b border-[#161924]">
                          <span className="text-slate-400">Map Tile Provider:</span>
                          <span className="text-white font-mono">CartoDB Voyager Raster XYZ API</span>
                        </div>

                        <div className="flex justify-between py-1.5 border-b border-[#161924]">
                          <span className="text-slate-400">Tactical Center Location:</span>
                          <span className="text-white font-bold">Nipani City, Belagavi District, Karnataka, India</span>
                        </div>

                        <div className="flex justify-between py-1.5 border-b border-[#161924]">
                          <span className="text-slate-400">Anchor Coordinates:</span>
                          <span className="text-blue-400 font-mono">16.4022° N, 74.3820° E</span>
                        </div>

                        <div className="flex justify-between py-1.5">
                          <span className="text-slate-400">Active Camera Matrix:</span>
                          <span className="text-slate-200">FEED-NIPANI-NORTH-01, FEED-NIPANI-HIGHWAY-02, FEED-NIPANI-CENTRAL-03</span>
                        </div>

                        <div className="pt-2">
                          <button
                            onClick={() => setShowMapModal(true)}
                            className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] text-blue-400 hover:text-white border border-blue-500/40 rounded-sm font-bold flex items-center gap-2 transition-colors"
                          >
                            <Icons.Map className="w-4 h-4" />
                            <span>LAUNCH TACTICAL RADAR MAP</span>
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Workspace Display Defaults */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">Analysis Workspace Defaults</h3>
                      
                      <div className="space-y-3">
                        <div className="flex items-center justify-between py-2 border-b border-[#161924]">
                          <div>
                            <div className="text-white font-bold text-xs">Default Target Engine</div>
                            <div className="text-slate-400 text-[10px]">Initial model selected when switching to Analysis Workspace</div>
                          </div>
                          <div className="flex gap-1 bg-[#11131A] p-1 rounded-sm border border-[#232838]">
                            <button
                              onClick={() => setAnalysisMode('anomaly')}
                              className={`px-2.5 py-1 rounded-sm text-[10px] font-bold ${analysisMode === 'anomaly' ? 'bg-blue-600 text-white' : 'text-slate-400'}`}
                            >
                              ANOMALY
                            </button>
                            <button
                              onClick={() => setAnalysisMode('vision_yolo')}
                              className={`px-2.5 py-1 rounded-sm text-[10px] font-bold ${analysisMode === 'vision_yolo' ? 'bg-blue-600 text-white' : 'text-slate-400'}`}
                            >
                              YOLO
                            </button>
                          </div>
                        </div>

                        <div className="flex items-center justify-between py-2 border-b border-[#161924]">
                          <div>
                            <div className="text-white font-bold text-xs">Temporal Evidence Timeline</div>
                            <div className="text-slate-400 text-[10px]">Synchronized playback playhead with red model attention windows</div>
                          </div>
                          <span className="text-emerald-400 text-[11px] font-bold">ENABLED (STEP 2E)</span>
                        </div>

                        <div className="flex items-center justify-between py-2">
                          <div>
                            <div className="text-white font-bold text-xs">Automatic Analysis Trigger</div>
                            <div className="text-slate-400 text-[10px]">Triggers inference automatically on first HTML5 play event</div>
                          </div>
                          <span className="text-blue-400 text-[11px] font-bold">ENABLED (STEP 2A)</span>
                        </div>
                      </div>
                    </div>

                  </div>
                )}

                {/* SUB-VIEW 5: DIAGNOSTICS */}
                {settingsTab === 'diagnostics' && (
                  <div className="max-w-4xl space-y-6">
                    
                    <div>
                      <h2 className="text-base font-bold text-white uppercase flex items-center gap-2">
                        <Icons.Zap className="w-4 h-4 text-cyan-400" />
                        <span>System Diagnostics &amp; Telemetry Probes</span>
                      </h2>
                      <p className="text-slate-400 text-xs mt-1 font-sans">
                        Execute real-time API latency probes, test neural model endpoint readiness, and inspect raw telemetry payloads.
                      </p>
                    </div>

                    {/* Diagnostics Probe Controller */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-bold text-white uppercase tracking-wider">End-to-End Pipeline Diagnostic Probe</h3>
                        <button
                          onClick={runFullDiagnostics}
                          disabled={isRunningDiagnostics}
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold rounded-sm flex items-center gap-2 transition-colors"
                        >
                          <Icons.RefreshCw className={`w-3.5 h-3.5 ${isRunningDiagnostics ? 'animate-spin' : ''}`} />
                          <span>{isRunningDiagnostics ? 'Running Probes...' : 'Execute Diagnostic Sweep'}</span>
                        </button>
                      </div>

                      {diagnosticLog && (
                        <div className="space-y-2 pt-2">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="text-slate-400">Diagnostic Telemetry Output (JSON):</span>
                            <button
                              onClick={() => copyToClipboard(JSON.stringify(diagnosticLog, null, 2))}
                              className="text-blue-400 hover:text-white flex items-center gap-1"
                            >
                              <Icons.Copy className="w-3 h-3" />
                              <span>Copy JSON</span>
                            </button>
                          </div>
                          <pre className="p-4 bg-[#08090C] rounded-sm border border-[#1E2232] text-emerald-400 text-[11px] overflow-x-auto max-h-96 font-mono">
                            {JSON.stringify(diagnosticLog, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>

                    {/* Model Integrity Table */}
                    <div className="p-5 bg-[#0D0E13] border border-[#1E2232] rounded-sm space-y-3">
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">Neural Checkpoint Verification</h3>

                      <div className="space-y-2 text-[11px]">
                        <div className="p-2.5 bg-[#11131A] rounded-sm border border-[#1E2232] flex items-center justify-between">
                          <span className="text-white font-bold">ResNet50-I3D Feature Extractor</span>
                          <span className="text-emerald-400 font-mono">model_i3d.pt (VERIFIED)</span>
                        </div>
                        <div className="p-2.5 bg-[#11131A] rounded-sm border border-[#1E2232] flex items-center justify-between">
                          <span className="text-white font-bold">Stage 1 Binary Detector Checkpoint</span>
                          <span className="text-emerald-400 font-mono">stage1_checkpoint.pt (VERIFIED)</span>
                        </div>
                        <div className="p-2.5 bg-[#11131A] rounded-sm border border-[#1E2232] flex items-center justify-between">
                          <span className="text-white font-bold">Stage 2 V2 Action Classifier Checkpoint</span>
                          <span className="text-emerald-400 font-mono">stage2_v2_checkpoint.pt (VERIFIED)</span>
                        </div>
                        <div className="p-2.5 bg-[#11131A] rounded-sm border border-[#1E2232] flex items-center justify-between">
                          <span className="text-white font-bold">YOLOv8 Real-Time Object Detector</span>
                          <span className="text-indigo-400 font-mono">yolov8n.pt (READY)</span>
                        </div>
                      </div>
                    </div>

                  </div>
                )}

              </div>

            </div>

          </div>
        )}

      </main>

      {/* TACTICAL GEOGRAPHIC LEAFLET MAP MODAL WITH CARTO VOYAGER API */}
      {showMapModal && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-4xl w-full h-[80vh] flex flex-col font-mono text-xs shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232] shrink-0">
              <div className="flex items-center gap-2">
                <Icons.Map className="w-4 h-4 text-blue-400" />
                <span className="font-bold text-white uppercase">TACTICAL GEOGRAPHIC MAP // CARTO VOYAGER</span>
                <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-sm border border-blue-500/20">
                  RASTER API ACTIVE
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => { setShowMapModal(false); openDispatchModal(); }}
                  className="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-sm font-bold flex items-center gap-1.5 transition-colors"
                >
                  <Icons.Radio className="w-3.5 h-3.5" />
                  <span>DISPATCH UNIT</span>
                </button>
                <button onClick={() => setShowMapModal(false)} className="text-slate-400 hover:text-white">
                  <Icons.X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="flex-1 relative bg-black">
              <div
                ref={mapContainerRef}
                className="absolute inset-0 w-full h-full"
              />

              <div className="absolute bottom-3 left-3 bg-[#0D0E13]/90 border border-[#232838] p-2.5 rounded-sm z-[500] text-[10px] space-y-1">
                <div className="text-white font-bold">LEGEND:</div>
                <div className="flex items-center gap-1.5 text-blue-400">
                  <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                  <span>Active Camera: {selectedSource.id}</span>
                </div>
                <div className="flex items-center gap-1.5 text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                  <span>Patrol Units (Active)</span>
                </div>
                <div className="flex items-center gap-1.5 text-amber-400">
                  <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                  <span>Stationary Units</span>
                </div>
              </div>

              <div className="absolute top-3 right-3 bg-[#0D0E13]/90 border border-[#232838] px-2.5 py-1 rounded-sm z-[500] text-[10px] text-slate-300">
                <span>API: <strong className="text-blue-400 font-mono">CartoDB Voyager Raster (Nipani)</strong></span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SET INCIDENT LOCATION MODAL (custom uploads only) */}
      {showIncidentLocationModal && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-md w-full flex flex-col font-mono text-xs shadow-2xl">
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232]">
              <div className="flex items-center gap-2">
                <Icons.Settings className="w-4 h-4 text-blue-400" />
                <span className="font-bold text-white uppercase">Set Incident Location</span>
              </div>
              <button onClick={() => setShowIncidentLocationModal(false)} className="text-slate-400 hover:text-white">
                <Icons.X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-3">
              <p className="text-slate-400 leading-relaxed">
                Paste a Google Maps link to the real incident location. This becomes the default
                location used for uploaded videos (including the one in the SMS sent to responders)
                until changed again.
              </p>

              <div className="bg-[#151822] border border-[#232838] rounded-sm p-2.5 text-slate-300">
                <div className="text-slate-500 mb-1">CURRENT DEFAULT:</div>
                <div className="text-white">{incidentLocation.label}</div>
                <div className="text-slate-500">{incidentLocation.lat.toFixed(6)}, {incidentLocation.lng.toFixed(6)}</div>
              </div>

              <input
                type="text"
                value={incidentLocationLinkInput}
                onChange={(e) => setIncidentLocationLinkInput(e.target.value)}
                placeholder="https://maps.app.goo.gl/..."
                className="w-full bg-[#151822] border border-[#232838] rounded-sm px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
              />

              {incidentLocationError && (
                <div className="text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-sm px-2.5 py-1.5">
                  {incidentLocationError}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 p-4 border-t border-[#1E2232]">
              <button
                onClick={() => setShowIncidentLocationModal(false)}
                className="px-3 py-2 rounded-sm bg-[#151822] hover:bg-[#1F2434] text-slate-300 border border-[#232838] transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!incidentLocationLinkInput.trim() || incidentLocationResolving}
                onClick={async () => {
                  setIncidentLocationError(null);
                  setIncidentLocationResolving(true);
                  try {
                    const result = await apiClient.resolveMapsLink(incidentLocationLinkInput.trim());
                    if (result?.success && result.latitude != null && result.longitude != null) {
                      const newLocation = {
                        lat: result.latitude,
                        lng: result.longitude,
                        label: result.label || `${result.latitude.toFixed(4)}, ${result.longitude.toFixed(4)}`,
                      };
                      setIncidentLocation(newLocation);
                      // If a custom upload is currently selected, update it immediately too.
                      if (customFile) {
                        setSelectedSource((prev) => ({
                          ...prev,
                          lat: newLocation.lat,
                          lng: newLocation.lng,
                          location: newLocation.label,
                        }));
                      }
                      setShowIncidentLocationModal(false);
                    } else {
                      setIncidentLocationError(result?.error || 'Could not resolve that link.');
                    }
                  } catch (err) {
                    setIncidentLocationError(err.message || 'Could not resolve that link.');
                  } finally {
                    setIncidentLocationResolving(false);
                  }
                }}
                className="px-3 py-2 rounded-sm bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/30 disabled:cursor-not-allowed text-white font-bold transition-colors"
              >
                {incidentLocationResolving ? 'Resolving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* INCIDENT DISPATCH & NEARBY RESPONDERS MODAL */}
      {showDispatchModal && (
        <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-3xl w-full flex flex-col font-mono text-xs shadow-2xl overflow-hidden max-h-[90vh]">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232] bg-[#11131A] shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse"></div>
                <span className="font-bold text-white uppercase tracking-wider">
                  INCIDENT RESPONSE // NEARBY RESPONDERS
                </span>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={openDispatchModal}
                  disabled={isLoadingNearby}
                  className="px-2.5 py-1 bg-[#151822] hover:bg-[#1F2434] text-slate-300 hover:text-white rounded-sm border border-[#232838] flex items-center gap-1 text-[11px] transition-colors"
                  title="Query /api/v1/dispatch/eligible"
                >
                  <Icons.RefreshCw className={`w-3 h-3 ${isLoadingNearby ? 'animate-spin' : ''}`} />
                  <span>REFRESH RADAR</span>
                </button>
                <button 
                  onClick={() => {
                    setShowDispatchModal(false);
                    setSelectedResponderForDispatch(null);
                    setDispatchOutcome(null);
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  <Icons.X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto space-y-6">
              
              {/* SECTION 1: NEARBY RESPONDERS LIST */}
              <div className="space-y-3">
                <div className="flex items-center justify-between pb-1 border-b border-[#1E2232]">
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    NEARBY RESPONDERS
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    GET /api/v1/dispatch/eligible
                  </span>
                </div>

                {isLoadingNearby ? (
                  <div className="p-8 text-center bg-[#11131A] rounded-sm border border-[#1E2232] space-y-2">
                    <Icons.RefreshCw className="w-5 h-5 text-blue-400 animate-spin mx-auto" />
                    <div className="text-slate-300 font-bold text-xs">QUERYING LIVE RESPONDER MATRIX...</div>
                  </div>
                ) : nearbyResponders.length === 0 ? (
                  /* HONEST EMPTY STATE - STRICTLY NO FAKE DATA */
                  <div className="p-8 text-center bg-[#11131A] rounded-sm border border-[#1E2232] space-y-3">
                    <div className="w-10 h-10 rounded-full bg-slate-800/60 border border-slate-700/60 flex items-center justify-center mx-auto text-slate-400">
                      <Icons.Radio className="w-5 h-5" />
                    </div>
                    <div className="space-y-1">
                      <div className="text-white font-bold text-xs tracking-wider">NO LIVE RESPONDERS</div>
                      <p className="text-slate-400 text-xs max-w-md mx-auto font-sans leading-relaxed">
                        No dispatchable responders are currently reporting their location.
                      </p>
                    </div>
                    <div className="pt-2 flex justify-center gap-3">
                      <button
                        onClick={() => {
                          setShowDispatchModal(false);
                          setView('tracker');
                        }}
                        className="px-3.5 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 border border-emerald-500/40 rounded-sm font-bold text-[11px] transition-colors flex items-center gap-1.5"
                      >
                        <Icons.Radio className="w-3.5 h-3.5" />
                        <span>OPEN RESPONDER TRACKER</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  /* ACTUAL RETURNED RESPONDERS CARDS */
                  <div className="space-y-2.5">
                    {nearbyResponders.map((responder) => {
                      const isSelected = selectedResponderForDispatch?.id === responder.id;
                      const liveState = (responder.live_state || (responder.status?.toLowerCase() === 'stale' ? 'stale' : responder.status?.toLowerCase() === 'offline' ? 'offline' : 'live')).toLowerCase();
                      const isLive = liveState === 'live' && (responder.status || '').toUpperCase() !== 'OFFLINE' && (responder.status || '').toUpperCase() !== 'STALE';
                      const lastUpdateStr = formatTimeAgo(
                        responder.last_seen_at || responder.last_location_update || responder.location?.timestamp || responder.timestamp
                      );
                      const distanceStr = getResponderDistanceStr(responder);
                      const phoneStr = maskPhoneNumber(responder.phone_number || responder.phone);

                      return (
                        <div
                          key={responder.id}
                          className={`p-3.5 rounded-sm border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                            isSelected
                              ? 'bg-blue-950/30 border-blue-500'
                              : 'bg-[#11131A] border-[#1E2232] hover:border-[#2C334A]'
                          }`}
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className={`w-2 h-2 rounded-full ${isLive ? 'bg-emerald-400' : liveState === 'stale' ? 'bg-amber-400' : 'bg-slate-500'}`}></span>
                              <span className={`text-[10px] font-bold ${isLive ? 'text-emerald-400' : liveState === 'stale' ? 'text-amber-400' : 'text-slate-400'}`}>
                                {isLive ? 'AVAILABLE' : liveState.toUpperCase()}
                              </span>
                            </div>
                            <div className="text-white font-bold text-xs">
                              {responder.name || responder.id}
                              {responder.role && <span className="text-slate-400 font-normal ml-2">({responder.role})</span>}
                            </div>
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-400 font-mono">
                              {distanceStr && <span className="text-blue-400 font-bold">{distanceStr}</span>}
                              {lastUpdateStr && <span>Location updated {lastUpdateStr}</span>}
                              {phoneStr && <span className="text-slate-300">{phoneStr}</span>}
                            </div>
                          </div>

                          <button
                            onClick={() => handleSelectResponderForDispatch(responder)}
                            className={`px-4 py-2 rounded-sm font-bold text-xs transition-colors shrink-0 ${
                              isSelected
                                ? 'bg-blue-600 text-white'
                                : isLive
                                ? 'bg-[#151822] hover:bg-[#1F2434] text-slate-200 border border-[#232838]'
                                : 'bg-[#151822] text-amber-400/80 border border-amber-500/30 hover:bg-[#1F2434]'
                            }`}
                          >
                            {isSelected ? 'SELECTED' : 'SELECT'}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* SECTION 2: DISPATCH PREVIEW & EXPLICIT SEND */}
              {selectedResponderForDispatch && (
                <div className="bg-[#11131A] border border-blue-500/40 p-4 rounded-sm space-y-4">
                  <div className="flex items-center justify-between pb-2 border-b border-[#1E2232]">
                    <span className="text-xs font-bold text-white uppercase tracking-wider">
                      SEND INCIDENT DETAILS
                    </span>
                    <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-sm border border-blue-500/20">
                      DISPATCH PREVIEW
                    </span>
                  </div>

                  {/* Recipient Details */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[11px]">
                    <div className="bg-[#0D0E13] p-2.5 rounded-sm border border-[#1E2232]">
                      <div className="text-[10px] text-slate-500 uppercase">Recipient</div>
                      <div className="font-bold text-white mt-0.5">{selectedResponderForDispatch.name || selectedResponderForDispatch.id}</div>
                    </div>
                    <div className="bg-[#0D0E13] p-2.5 rounded-sm border border-[#1E2232]">
                      <div className="text-[10px] text-slate-500 uppercase">Phone</div>
                      <div className="font-bold text-blue-400 mt-0.5 font-mono">
                        {maskPhoneNumber(selectedResponderForDispatch.phone_number || selectedResponderForDispatch.phone) || 'N/A'}
                      </div>
                    </div>
                    <div className="bg-[#0D0E13] p-2.5 rounded-sm border border-[#1E2232]">
                      <div className="text-[10px] text-slate-500 uppercase">Distance</div>
                      <div className="font-bold text-emerald-400 mt-0.5">
                        {getResponderDistanceStr(selectedResponderForDispatch) || 'Nearby'}
                      </div>
                    </div>
                  </div>

                  {/* Message Preview Box */}
                  <div className="space-y-1.5">
                    <div className="text-[10px] text-slate-400 uppercase font-bold">Message Preview</div>
                    <div className="p-3.5 bg-[#08090C] rounded-sm border border-[#1E2232] text-slate-200 font-mono text-xs whitespace-pre-wrap leading-relaxed">
                      {dispatchPreviewMessage}
                    </div>
                  </div>

                  {/* Stale Responder Guard */}
                  {selectedResponderForDispatch && (selectedResponderForDispatch.live_state === 'stale' || selectedResponderForDispatch.live_state === 'offline' || (selectedResponderForDispatch.status || '').toUpperCase() === 'STALE' || (selectedResponderForDispatch.status || '').toUpperCase() === 'OFFLINE') ? (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-sm text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-amber-400 font-bold">
                        <Icons.AlertTriangle className="w-4 h-4 shrink-0" />
                        <span>RESPONDER NO LONGER LIVE</span>
                      </div>
                      <button
                        onClick={openDispatchModal}
                        className="px-2.5 py-1 bg-[#151822] hover:bg-[#1F2434] text-amber-300 border border-amber-500/40 rounded-sm text-[11px] font-bold transition-colors"
                      >
                        Refresh Nearby Responders
                      </button>
                    </div>
                  ) : null}

                  {/* Outcome Status */}
                  {dispatchOutcome && (
                    <div className={`p-3 rounded-sm border text-xs flex items-center gap-2 ${
                      dispatchOutcome.status === 'success'
                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                        : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                    }`}>
                      {dispatchOutcome.status === 'success' ? (
                        <Icons.CheckCircle className="w-4 h-4 shrink-0" />
                      ) : (
                        <Icons.AlertTriangle className="w-4 h-4 shrink-0" />
                      )}
                      <span className="font-bold uppercase tracking-wide">
                        {dispatchOutcome.status === 'success' ? 'SMS DISPATCHED' : 'DISPATCH FAILED'}
                      </span>
                      <span className="text-slate-300 font-normal">
                        — {dispatchOutcome.message || dispatchOutcome.error}
                      </span>
                    </div>
                  )}

                  {/* Explicit Action Buttons */}
                  <div className="flex items-center justify-end gap-3 pt-2">
                    <button
                      onClick={() => {
                        setSelectedResponderForDispatch(null);
                        setDispatchOutcome(null);
                      }}
                      className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] text-slate-300 hover:text-white rounded-sm font-bold text-xs transition-colors"
                    >
                      CANCEL
                    </button>
                    
                    {!(selectedResponderForDispatch.live_state === 'stale' || selectedResponderForDispatch.live_state === 'offline' || (selectedResponderForDispatch.status || '').toUpperCase() === 'STALE' || (selectedResponderForDispatch.status || '').toUpperCase() === 'OFFLINE') ? (
                      <button
                        onClick={handleSendDispatch}
                        disabled={isSendingDispatch}
                        className="px-5 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold rounded-sm text-xs transition-all flex items-center gap-2 shadow-lg shadow-rose-600/20 uppercase tracking-wider"
                      >
                        <Icons.Send className={`w-3.5 h-3.5 ${isSendingDispatch ? 'animate-spin' : ''}`} />
                        <span>{isSendingDispatch ? 'SENDING...' : 'SEND SMS'}</span>
                      </button>
                    ) : (
                      <button
                        disabled={true}
                        className="px-5 py-2 bg-slate-800 text-slate-500 rounded-sm font-bold text-xs cursor-not-allowed uppercase tracking-wider"
                      >
                        CANNOT DISPATCH (STALE)
                      </button>
                    )}
                  </div>

                </div>
              )}

            </div>

          </div>
        </div>
      )}

      {/* ADD OFFICER MODAL */}
      {showAddOfficerModal && (
        <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-lg w-full font-mono text-xs shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232] bg-[#11131A]">
              <div className="flex items-center gap-2">
                <Icons.Plus className="w-4 h-4 text-emerald-400" />
                <span className="font-bold text-white uppercase tracking-wider">REGISTER FIELD OFFICER</span>
              </div>
              <button
                onClick={() => setShowAddOfficerModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <Icons.X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleAddOfficerSubmit} className="p-5 space-y-4">
              {addOfficerError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-sm text-rose-300 text-xs flex items-center gap-2">
                  <Icons.AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                  <span>{addOfficerError}</span>
                </div>
              )}

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">
                  Full Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={addOfficerForm.name}
                  onChange={(e) => setAddOfficerForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Rahul Kumar"
                  className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">
                    Officer ID (Optional)
                  </label>
                  <input
                    type="text"
                    value={addOfficerForm.id}
                    onChange={(e) => setAddOfficerForm(f => ({ ...f, id: e.target.value }))}
                    placeholder="e.g. OFF-001"
                    className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">
                    Mobile Number
                  </label>
                  <input
                    type="tel"
                    value={addOfficerForm.phone_number}
                    onChange={(e) => setAddOfficerForm(f => ({ ...f, phone_number: e.target.value }))}
                    placeholder="e.g. +919876543210"
                    className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">
                    Role / Title
                  </label>
                  <input
                    type="text"
                    value={addOfficerForm.role}
                    onChange={(e) => setAddOfficerForm(f => ({ ...f, role: e.target.value }))}
                    placeholder="e.g. Police Officer"
                    className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">
                    Unit / Sector (Optional)
                  </label>
                  <input
                    type="text"
                    value={addOfficerForm.unit}
                    onChange={(e) => setAddOfficerForm(f => ({ ...f, unit: e.target.value }))}
                    placeholder="e.g. Sector 4 Patrol"
                    className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-[#1E2232]">
                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">
                    Duty Login Username <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    minLength={3}
                    value={addOfficerForm.username}
                    onChange={(e) => setAddOfficerForm(f => ({ ...f, username: e.target.value }))}
                    placeholder="e.g. rahul.kumar"
                    autoComplete="off"
                    className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                  />
                </div>

                <div>
                  <label className="text-[11px] text-slate-400 block mb-1">
                    Duty Login Password <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={addOfficerForm.password}
                    onChange={(e) => setAddOfficerForm(f => ({ ...f, password: e.target.value }))}
                    placeholder="min. 8 characters"
                    autoComplete="off"
                    className="w-full bg-[#151822] border border-[#232838] focus:border-emerald-500/60 rounded-sm px-3 py-2 text-white font-mono text-xs focus:outline-none"
                  />
                </div>
              </div>
              <p className="text-[10px] text-slate-500 -mt-1">
                Used by the officer to log in on the mobile duty page before starting/ending duty. Shown once after registration.
              </p>

              <div className="pt-3 border-t border-[#1E2232] flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setShowAddOfficerModal(false)}
                  className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] text-slate-300 rounded-sm transition-colors"
                >
                  CANCEL
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingOfficer}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold rounded-sm flex items-center gap-1.5 transition-colors shadow-md shadow-emerald-600/20"
                >
                  {isSubmittingOfficer ? (
                    <>
                      <Icons.RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>REGISTERING...</span>
                    </>
                  ) : (
                    <span>REGISTER OFFICER</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ONE-TIME DUTY LOGIN CREDENTIALS REVEAL -- shown once right after
          registration, never recoverable again (same discipline as the PIN
          reveal elsewhere in this app). */}
      {createdOfficerCredentials && (
        <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-emerald-500/40 rounded-sm max-w-md w-full font-mono text-xs shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232] bg-[#11131A]">
              <div className="flex items-center gap-2">
                <Icons.CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="font-bold text-white uppercase tracking-wider">Officer Registered</span>
              </div>
              <button
                onClick={() => setCreatedOfficerCredentials(null)}
                className="text-slate-400 hover:text-white"
              >
                <Icons.X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-sm text-amber-300 text-xs flex items-start gap-2">
                <Icons.AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
                <span>Share this password with {createdOfficerCredentials.name} now. It will not be shown again -- only reissuable by registering a new password via Edit.</span>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between bg-[#151822] border border-[#232838] rounded-sm px-3 py-2">
                  <span className="text-slate-400">Username</span>
                  <span className="text-white font-bold">{createdOfficerCredentials.username}</span>
                </div>
                <div className="flex items-center justify-between bg-[#151822] border border-[#232838] rounded-sm px-3 py-2">
                  <span className="text-slate-400">Password</span>
                  <span className="text-white font-bold">{createdOfficerCredentials.password}</span>
                </div>
              </div>
              <div className="pt-2 flex items-center justify-end">
                <button
                  onClick={() => setCreatedOfficerCredentials(null)}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-sm transition-colors shadow-md shadow-emerald-600/20"
                >
                  DONE
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SEND DUTY LINK CONFIRMATION MODAL */}
      {sendDutyLinkModalOfficer && (
        <div className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-4">
          <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-md w-full font-mono text-xs shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[#1E2232] bg-[#11131A]">
              <div className="flex items-center gap-2 text-white font-bold uppercase tracking-wider">
                <Icons.Smartphone className="w-4 h-4 text-emerald-400" />
                <span>SEND DUTY LINK?</span>
              </div>
              <button
                onClick={() => setSendDutyLinkModalOfficer(null)}
                className="text-slate-400 hover:text-white"
              >
                <Icons.X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {/* Officer Details Preview */}
              <div className="bg-[#11131A] p-3.5 rounded-sm border border-[#1E2232] space-y-2">
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block">Officer:</span>
                  <span className="text-white font-bold text-sm">{sendDutyLinkModalOfficer.name || sendDutyLinkModalOfficer.id}</span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block">Mobile:</span>
                  <span className="text-emerald-400 font-bold font-mono">
                    {maskPhoneNumber(sendDutyLinkModalOfficer.phone_number || sendDutyLinkModalOfficer.phone)}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] text-slate-500 uppercase block">Role &amp; ID:</span>
                  <span className="text-slate-300">{sendDutyLinkModalOfficer.role || 'Police Officer'} ({sendDutyLinkModalOfficer.id})</span>
                </div>
              </div>

              <div className="text-slate-400 text-xs font-sans leading-relaxed">
                This sends an SMS containing the secure duty link to the officer's registered mobile device.
              </div>

              <div className="p-2.5 bg-[#08090C] rounded-sm border border-[#1E2232] text-[11px] text-slate-400 break-all font-mono">
                <span className="text-slate-500 block text-[10px] uppercase">Secure Duty Target URL:</span>
                <span className="text-blue-400">
                  {typeof window !== 'undefined' ? `${window.location.origin}/responder/duty/${encodeURIComponent(sendDutyLinkModalOfficer.id)}` : ''}
                </span>
              </div>

              {/* Status outcome banner */}
              {dutyLinkOutcome && (
                <div className={`p-3 rounded-sm border text-xs space-y-1 ${
                  dutyLinkOutcome.success
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}>
                  <div className="font-bold font-mono flex items-center gap-1.5">
                    {dutyLinkOutcome.success ? (
                      <>
                        <Icons.CheckCircle className="w-4 h-4 text-emerald-400" />
                        <span>DUTY LINK SENT</span>
                      </>
                    ) : (
                      <>
                        <Icons.AlertTriangle className="w-4 h-4 text-rose-400" />
                        <span>DUTY LINK NOT SENT</span>
                      </>
                    )}
                  </div>
                  {dutyLinkOutcome.detail && <p className="font-sans">{dutyLinkOutcome.detail}</p>}
                  {dutyLinkOutcome.error && <p className="font-sans">{dutyLinkOutcome.error}</p>}
                </div>
              )}

              {/* Action Buttons */}
              <div className="pt-3 border-t border-[#1E2232] flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setSendDutyLinkModalOfficer(null)}
                  className="px-4 py-2 bg-[#151822] hover:bg-[#1F2434] text-slate-300 rounded-sm transition-colors"
                >
                  {dutyLinkOutcome?.success ? 'CLOSE' : 'CANCEL'}
                </button>

                {!dutyLinkOutcome?.success && (
                  <button
                    type="button"
                    onClick={handleConfirmSendDutyLink}
                    disabled={isSendingDutyLink}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold rounded-sm flex items-center gap-1.5 transition-colors shadow-md shadow-emerald-600/20"
                  >
                    {isSendingDutyLink ? (
                      <>
                        <Icons.RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>SENDING SMS...</span>
                      </>
                    ) : (
                      <span>CONFIRM &amp; SEND SMS</span>
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* (Former standalone "LOG JSON INSPECTOR MODAL" removed -- its one
          caller was deleted when the Audit Trail view's two tables were
          merged into one; SESSION EVENT DETAIL MODAL below now covers
          every row, job-history rows included.) */}

      {/* SESSION EVENT DETAIL MODAL -- expands one Session Events audit row.
          Every field is read directly off that entry's real `details`
          payload (see dispatch.py's send_dispatch audit_repo.log call) --
          never fabricated. A dispatch_sent/dispatch_failed entry carries
          incident place, officer name/phone, and incident type/confidence;
          the short clip is only recoverable if the source job is still in
          jobSourceInfoRef (i.e. analyzed this browser session) -- the
          backend never persists the uploaded video itself. Other event
          types (responder CRUD, SMS config changes, etc.) show whatever
          their own `details` dict actually carries, with an honest "not
          applicable" for fields that event type doesn't have. */}
      {selectedAuditEntry && (() => {
        const d = selectedAuditEntry.details || {};
        const jobId = d.job_id || null;
        const sourceInfo = jobId ? jobSourceInfoRef.current[jobId] : null;
        // Last-resort fallback: older dispatch_sent entries recorded before
        // incident_location_label existed as its own field still have the
        // human-readable place name embedded in the SMS body itself (see
        // dispatch.py's _build_incident_message -- "Location: <label>").
        // Never fabricated: only used when the structured field is absent.
        const messageLocationMatch = typeof d.message === 'string'
          ? d.message.match(/Location:\s*([^\n]+)/)
          : null;
        const placeLabel = d.incident_location_label
          || sourceInfo?.locationLabel
          || (messageLocationMatch && messageLocationMatch[1].trim() !== 'LOCATION NOT CONFIGURED'
            ? messageLocationMatch[1].trim()
            : null)
          || (d.incident_latitude != null && d.incident_longitude != null
            ? `${d.incident_latitude.toFixed(5)}, ${d.incident_longitude.toFixed(5)}`
            : null);
        const hasOfficer = Boolean(d.responder_name || d.responder_phone || d.responder_id);

        return (
          <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4">
            <div className="bg-[#0D0E13] border border-[#232838] rounded-sm max-w-xl w-full p-6 space-y-4 font-mono text-xs max-h-[85vh] overflow-y-auto">
              <div className="flex items-center justify-between pb-3 border-b border-[#1E2232]">
                <div>
                  <h3 className="font-bold text-white uppercase">
                    {selectedAuditEntry.event_type.replace(/_/g, ' ')}
                  </h3>
                  <p className="text-slate-500 text-[10px] mt-0.5">{selectedAuditEntry.timestamp}</p>
                </div>
                <button onClick={() => setSelectedAuditEntry(null)} className="text-slate-400 hover:text-white">
                  <Icons.X className="w-4 h-4" />
                </button>
              </div>

              {selectedAuditEntry.summary && (
                <p className="font-sans text-slate-300">{selectedAuditEntry.summary}</p>
              )}

              {/* INCIDENT PLACE */}
              <div className="bg-[#08090C] border border-[#1E2232] rounded-sm p-3 space-y-1">
                <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase">
                  <Icons.MapPin className="w-3.5 h-3.5" />
                  <span>Incident Location</span>
                </div>
                {placeLabel ? (
                  <>
                    <div className="text-white font-bold">{placeLabel}</div>
                    {d.incident_latitude != null && d.incident_longitude != null && (
                      <a
                        href={`https://maps.google.com/?q=${d.incident_latitude},${d.incident_longitude}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-400 hover:text-blue-300 underline text-[11px]"
                      >
                        {d.incident_latitude.toFixed(5)}, {d.incident_longitude.toFixed(5)} -- open in Maps
                      </a>
                    )}
                  </>
                ) : (
                  <div className="text-slate-500">Not recorded for this event.</div>
                )}
              </div>

              {/* OFFICER / RESPONDER */}
              <div className="bg-[#08090C] border border-[#1E2232] rounded-sm p-3 space-y-1">
                <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase">
                  <Icons.Shield className="w-3.5 h-3.5" />
                  <span>Responding Officer</span>
                </div>
                {hasOfficer ? (
                  <>
                    <div className="text-white font-bold">{d.responder_name || `Officer ${d.responder_id}`}</div>
                    <div className="text-slate-400">
                      ID: {d.responder_id || '—'}
                    </div>
                    {d.responder_phone ? (
                      <a
                        href={`tel:${d.responder_phone}`}
                        className="text-emerald-400 hover:text-emerald-300 underline inline-flex items-center gap-1"
                      >
                        <Icons.Phone className="w-3 h-3" />
                        {d.responder_phone}
                      </a>
                    ) : (
                      <div className="text-slate-500">No phone number on file.</div>
                    )}
                  </>
                ) : (
                  <div className="text-slate-500">No responder associated with this event.</div>
                )}
              </div>

              {/* INCIDENT TYPE / CONFIDENCE */}
              {(d.incident_type || d.confidence != null) && (
                <div className="bg-[#08090C] border border-[#1E2232] rounded-sm p-3 space-y-1">
                  <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase">
                    <Icons.AlertTriangle className="w-3.5 h-3.5" />
                    <span>Incident</span>
                  </div>
                  <div className="text-white font-bold">{d.incident_type || 'Unspecified'}</div>
                  {d.confidence != null && (
                    <div className="text-amber-400">
                      Confidence: {(d.confidence <= 1 ? d.confidence * 100 : d.confidence).toFixed(1)}%
                    </div>
                  )}
                </div>
              )}

              {/* SHORT CLIP OF THE ANOMALY */}
              <div className="bg-[#08090C] border border-[#1E2232] rounded-sm p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-slate-500 text-[10px] uppercase">
                  <Icons.Video className="w-3.5 h-3.5" />
                  <span>Anomaly Clip</span>
                </div>
                {sourceInfo?.videoUrl ? (
                  <video
                    key={sourceInfo.videoUrl}
                    src={sourceInfo.videoUrl}
                    controls
                    className="w-full rounded-sm border border-[#1E2232] max-h-64 bg-black"
                  />
                ) : (
                  <div className="text-slate-500">
                    No clip available -- the source video for this job is only kept in memory for the
                    browser session it was analyzed in{jobId ? ` (job ${jobId})` : ''}, and that session has ended.
                  </div>
                )}
              </div>

              {/* FULL RAW DETAILS -- same JSON-inspector affordance already
                  used by the Job History table above, so every field this
                  event actually recorded stays reachable even if not called
                  out in a dedicated section. */}
              <details className="bg-[#08090C] border border-[#1E2232] rounded-sm p-3">
                <summary className="text-slate-500 text-[10px] uppercase cursor-pointer">
                  Raw Event Details
                </summary>
                <pre className="text-emerald-400 overflow-x-auto mt-2 text-[11px]">
                  {JSON.stringify(selectedAuditEntry, null, 2)}
                </pre>
              </details>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  onClick={() => copyToClipboard(JSON.stringify(selectedAuditEntry, null, 2))}
                  className="px-4 py-1.5 bg-[#151822] hover:bg-[#1F2434] text-white rounded-sm flex items-center gap-1.5"
                >
                  <Icons.Copy className="w-3.5 h-3.5" />
                  <span>Copy JSON</span>
                </button>
                <button
                  onClick={() => setSelectedAuditEntry(null)}
                  className="px-4 py-1.5 bg-[#151822] hover:bg-[#1F2434] text-white rounded-sm"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        );
      })()}

    </div>
  );
}
