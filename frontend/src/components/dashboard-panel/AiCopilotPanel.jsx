import React, { useEffect, useRef, useState } from 'react';
import { Icons } from '../../App';

function Pct({ value }) {
  if (value == null) return <span className="text-slate-500">N/A</span>;
  return <span>{(value * 100).toFixed(1)}%</span>;
}

/**
 * Reveals `text` character-by-character, chatbot-style -- purely a
 * presentation effect over text that already arrived from the real
 * backend fetch. Never fabricates or alters the text itself, only the
 * pace it's drawn on screen; a trailing caret blinks while revealing.
 * Resets and re-plays whenever `text` changes to a new value (new
 * incident, or a Refresh-triggered re-summarization).
 */
function TypewriterText({ text, className }) {
  const [shown, setShown] = useState('');
  const textRef = useRef(text);

  useEffect(() => {
    textRef.current = text;
    setShown('');
    if (!text) return undefined;

    let i = 0;
    // ~18ms/char -- fast enough to feel immediate on a short summary,
    // still visibly "typed" rather than an instant paste.
    const intervalId = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) clearInterval(intervalId);
    }, 18);

    return () => clearInterval(intervalId);
  }, [text]);

  const done = shown.length >= (text?.length || 0);

  return (
    <p className={className}>
      {shown}
      {!done && <span className="inline-block w-[2px] h-3 bg-blue-400 ml-0.5 align-middle animate-pulse" />}
    </p>
  );
}

/**
 * AI COPILOT tab: a real, backend-proxied Grok (xAI) incident summarizer --
 * NOT a conversational chatbot. Summarization only, scoped exactly to the
 * latest real incident (GET /v1/incidents/latest/summary/ai, see
 * app/services/grok_summary_service.py). Every value rendered here comes
 * from that fetch; nothing is fabricated client-side.
 *
 * Re-fetches automatically when the active job's identity changes (new
 * analysis completed) and once on mount -- no polling/interval timer, so
 * this never calls Grok repeatedly on a render/poll tick. A "Refresh"
 * button lets the operator force a new Grok call for the same incident.
 */
export default function AiCopilotPanel({ activeJob, aiSummary, aiSummaryLoading, aiSummaryError, refreshAiSummary }) {
  // Fetch once on mount -- shows whatever the latest incident already is
  // (e.g. from a previous session) even if no job has run yet this
  // session. This is independent of the completion-triggered re-fetch
  // below.
  const hasFetchedOnMountRef = useRef(false);
  useEffect(() => {
    if (hasFetchedOnMountRef.current) return;
    hasFetchedOnMountRef.current = true;
    refreshAiSummary(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Tracks the job this panel last fetched a summary for on completion,
  // keyed on BOTH jobId and status. Keying on jobId alone would fire the
  // instant a job starts (queued/processing) -- long before DETECTION
  // DATA has a result to show. Keying on status too means this fires
  // exactly when activeJob.status flips to 'completed', the same real-
  // data moment DETECTION DATA's own result becomes available -- so the
  // AI summary request goes out in parallel with (not after) that
  // render, and the two tabs arrive at a result at roughly the same time
  // instead of the AI tab lagging behind by a user-triggered extra round
  // trip.
  const lastFetchedKeyRef = useRef(undefined);

  useEffect(() => {
    const currentJobId = activeJob?.jobId ?? null;
    const currentStatus = activeJob?.status ?? null;
    const key = currentStatus === 'completed' ? `${currentJobId}:completed` : null;
    if (key === null || lastFetchedKeyRef.current === key) return;
    lastFetchedKeyRef.current = key;
    refreshAiSummary(false);
    // Only re-run when the job's completed-identity actually changes --
    // refreshAiSummary itself is a stable useCallback from the hook.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJob?.jobId, activeJob?.status]);

  const incident = aiSummary?.incident || null;
  const incidentSummary = aiSummary?.summary || null;
  const summaryText = aiSummary?.ai_summary_text || null;
  const summarySource = aiSummary?.ai_summary_source || null;
  const location = incidentSummary?.location;
  const hasLocation = location?.available && location?.label;

  return (
    <div className="flex-1 flex flex-col overflow-y-auto space-y-4 font-mono text-xs">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-slate-500 uppercase font-bold flex items-center gap-1.5">
          <Icons.Bot className="w-3.5 h-3.5 text-blue-400" />
          AI Incident Summary
        </span>
        <button
          onClick={() => refreshAiSummary(true)}
          disabled={aiSummaryLoading}
          className="flex items-center gap-1.5 text-[10px] text-slate-400 hover:text-white px-2 py-1 rounded-sm border border-[#232838] hover:border-slate-600 transition-colors disabled:opacity-50"
        >
          <Icons.RefreshCw className={`w-3 h-3 ${aiSummaryLoading ? 'animate-spin' : ''}`} />
          REFRESH
        </button>
      </div>

      {aiSummaryLoading && !aiSummary && (
        <div className="p-3.5 rounded-sm border bg-[#11131A] border-[#1E2232] flex items-center gap-2 text-blue-400">
          <Icons.Bot className="w-4 h-4 shrink-0" />
          <span className="flex items-center gap-1">
            <span>Generating incident summary</span>
            <span className="flex gap-0.5">
              <span className="w-1 h-1 rounded-full bg-blue-400 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1 h-1 rounded-full bg-blue-400 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1 h-1 rounded-full bg-blue-400 animate-bounce" />
            </span>
          </span>
        </div>
      )}

      {!aiSummaryLoading && aiSummaryError && !aiSummary && (
        <div className="p-3.5 rounded-sm border bg-rose-500/10 border-rose-500/30 text-rose-400">
          <div className="font-bold text-xs flex items-center gap-2">
            <Icons.AlertTriangle className="w-4 h-4" />
            SUMMARY UNAVAILABLE
          </div>
          <p className="text-[11px] text-slate-300 mt-1 font-sans">{aiSummaryError}</p>
        </div>
      )}

      {!aiSummaryError && aiSummary && !incident && (
        <div className="p-4 rounded-sm border bg-[#11131A] border-[#1E2232] text-slate-400 text-center">
          No incidents recorded yet. A summary will appear here once an incident is detected.
        </div>
      )}

      {incident && incidentSummary && (
        <div className="space-y-3">
          {/* Prose summary + source badge */}
          <div className="p-3.5 rounded-sm border bg-[#11131A] border-[#1E2232] space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-slate-500 uppercase font-bold">Summary</span>
              {summarySource === 'grok' ? (
                <span className="text-[9px] px-1.5 py-0.5 bg-blue-500/20 text-blue-300 border border-blue-500/40 rounded-sm font-bold uppercase">
                  GROK
                </span>
              ) : summarySource === 'fallback' ? (
                <span className="text-[9px] px-1.5 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded-sm font-bold uppercase">
                  FALLBACK SUMMARY (AI UNAVAILABLE)
                </span>
              ) : null}
            </div>
            {summaryText ? (
              <TypewriterText
                text={summaryText}
                className="text-xs text-slate-100 font-sans leading-relaxed whitespace-pre-wrap"
              />
            ) : (
              <p className="text-xs text-slate-100 font-sans leading-relaxed whitespace-pre-wrap">
                No summary text available.
              </p>
            )}
            {aiSummaryLoading && (
              <div className="text-[10px] text-slate-500">Refreshing...</div>
            )}
          </div>

          {/* Structured breakdown -- model predictions vs verified facts,
              reused from the old IncidentAssistantPanel's layout. */}
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 rounded-sm border bg-[#11131A] border-[#1E2232] text-center">
              <div className="text-[9px] text-slate-500 uppercase">Anomaly</div>
              <div className="text-base font-bold text-rose-400 mt-1">
                <Pct value={incidentSummary.ai_detected.anomaly_probability} />
              </div>
            </div>
            <div className="p-2.5 rounded-sm border bg-[#11131A] border-[#1E2232] text-center">
              <div className="text-[9px] text-slate-500 uppercase">Likely Action</div>
              <div className="text-xs font-bold text-blue-400 mt-1 truncate">
                {incidentSummary.ai_detected.likely_action || 'N/A'}
              </div>
            </div>
            <div className="p-2.5 rounded-sm border bg-[#11131A] border-[#1E2232] text-center">
              <div className="text-[9px] text-slate-500 uppercase">Confidence</div>
              <div className="text-base font-bold text-emerald-400 mt-1">
                <Pct value={incidentSummary.ai_detected.action_confidence} />
              </div>
            </div>
          </div>

          <div className="p-3 rounded-sm border bg-[#11131A] border-[#1E2232] flex items-center gap-2">
            <Icons.MapPin className="w-3.5 h-3.5 text-rose-400 shrink-0" />
            <span className="text-[11px] text-slate-300">
              {hasLocation ? location.label : 'Location unavailable'}
            </span>
          </div>

          {incidentSummary.limitations?.length > 0 && (
            <div className="p-2.5 rounded-sm border bg-amber-500/10 border-amber-500/30 space-y-1">
              <span className="text-[9px] text-amber-400 uppercase font-bold">Limitations</span>
              <ul className="text-[10px] text-slate-300 font-sans list-disc list-inside space-y-0.5">
                {incidentSummary.limitations.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
