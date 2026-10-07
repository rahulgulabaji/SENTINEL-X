import type { TemporalEvidence } from "../../types/anomaly";
import { Icons } from "./icons";

/**
 * Real temporal-evidence timeline. Renders the per-window attention
 * weights the existing whole-video models already produce internally
 * (GatedAttentionMIL for stage1, TemporalAttention for stage2), positioned
 * at their real source-video timestamps.
 *
 * This is explicitly NOT a per-window classification. Both models were
 * trained as whole-video sequence classifiers -- the WHOLE-VIDEO
 * ASSESSMENT panel elsewhere is the only authoritative anomaly/action
 * result. These bars only show relative model attention: "where did the
 * model look while producing that one result", not "what did the model
 * decide about this window".
 *
 * No fabricated data: if `evidence.available` is false or there are no
 * windows, this renders an honest empty state instead of invented bars.
 */
export function TemporalEvidenceTimeline({
  evidence,
  currentTime,
  duration,
}: {
  evidence: TemporalEvidence;
  currentTime: number;
  duration: number | null;
}) {
  const hasWindows = evidence.available && evidence.windows.length > 0;
  const hasStage2 = hasWindows && evidence.windows.some((w) => w.stage2_attention_normalized !== null);
  const effectiveDuration = duration ?? (hasWindows ? evidence.windows[evidence.windows.length - 1].end_time_seconds : null);

  return (
    <div className="shrink-0 border border-border rounded-sm bg-surface-1 p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[11px] font-semibold text-text-primary tracking-wide flex items-center gap-1.5">
          <Icons.Zap className="w-3.5 h-3.5 text-accent" />
          TEMPORAL MODEL EVIDENCE
        </div>
        {hasWindows && (
          <div className="text-[10px] text-text-tertiary">{evidence.windows.length} windows &middot; {evidence.window_duration_seconds.toFixed(1)}s each</div>
        )}
      </div>

      {!hasWindows ? (
        <div className="flex flex-col items-center gap-1.5 py-5 text-center">
          <Icons.AlertTriangle className="w-5 h-5 text-text-tertiary" />
          <div className="font-mono text-[11px] font-semibold text-text-secondary">NO TEMPORAL EVIDENCE AVAILABLE</div>
          <div className="text-[10px] text-text-tertiary max-w-[320px]">
            Run an analysis to see which temporal portions of the video received stronger model attention.
          </div>
        </div>
      ) : (
        <>
          <div className="text-[10px] text-text-tertiary leading-snug">
            Relative model attention per window, not a per-window classification. The whole-video result above remains authoritative.
          </div>

          <TimelineRow
            label="ANOMALY EVIDENCE (stage 1 attention)"
            colorClass="bg-accent"
            evidence={evidence}
            effectiveDuration={effectiveDuration}
            currentTime={currentTime}
            valueKey="stage1_attention_normalized"
          />

          {hasStage2 && (
            <TimelineRow
              label="ACTION MODEL ATTENTION (stage 2 attention)"
              colorClass="bg-sev-moderate"
              evidence={evidence}
              effectiveDuration={effectiveDuration}
              currentTime={currentTime}
              valueKey="stage2_attention_normalized"
            />
          )}
        </>
      )}
    </div>
  );
}

function TimelineRow({
  label,
  colorClass,
  evidence,
  effectiveDuration,
  currentTime,
  valueKey,
}: {
  label: string;
  colorClass: string;
  evidence: TemporalEvidence;
  effectiveDuration: number | null;
  currentTime: number;
  valueKey: "stage1_attention_normalized" | "stage2_attention_normalized";
}) {
  const playheadFraction = effectiveDuration && effectiveDuration > 0 ? Math.min(1, Math.max(0, currentTime / effectiveDuration)) : null;

  return (
    <div className="flex flex-col gap-1">
      <div className="text-[10px] font-mono text-text-tertiary">{label}</div>
      <div className="relative h-10 bg-surface-0 border border-border rounded-sm overflow-hidden">
        <div className="absolute inset-0 flex items-stretch">
          {evidence.windows.map((w) => {
            const value = w[valueKey];
            const left = effectiveDuration ? (w.start_time_seconds / effectiveDuration) * 100 : 0;
            const width = effectiveDuration ? ((w.end_time_seconds - w.start_time_seconds) / effectiveDuration) * 100 : 0;
            const heightPct = value != null ? Math.max(4, value * 100) : 4;
            return (
              <div
                key={w.window_index}
                className="absolute bottom-0 flex items-end"
                style={{ left: `${left}%`, width: `${width}%` }}
                title={`Window ${w.window_index}: ${w.start_time_seconds.toFixed(1)}s - ${w.end_time_seconds.toFixed(1)}s, attention ${value != null ? value.toFixed(3) : "n/a"}`}
              >
                <div className={`w-full mx-[1px] opacity-70 ${colorClass}`} style={{ height: `${heightPct}%` }} />
              </div>
            );
          })}
        </div>
        {playheadFraction !== null && (
          <div
            className="absolute top-0 bottom-0 w-[2px] bg-white"
            style={{ left: `${playheadFraction * 100}%` }}
          />
        )}
      </div>
    </div>
  );
}
