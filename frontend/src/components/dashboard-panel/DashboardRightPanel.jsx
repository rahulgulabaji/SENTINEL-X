import React, { useState } from 'react';
import { Icons } from '../../App';
import AnalysisResultsPanel from '../incident-assistant/AnalysisResultsPanel';
import AiCopilotPanel from './AiCopilotPanel';

/**
 * Thin tab-strip wrapper for the Analysis Workspace's right column.
 * Exactly two tabs -- AI COPILOT and DETECTION DATA -- switching content
 * inside the same panel, no navigation/route change. Replaces the
 * previous direct <AnalysisResultsPanel> render; DETECTION DATA renders
 * that component completely unchanged (same props, same behavior), AI
 * COPILOT renders the new real Grok-backed summarizer.
 *
 * Default tab is DETECTION DATA -- least surprise, preserves "open
 * Analysis and see the Intelligence Panel" as the default view.
 */
export default function DashboardRightPanel({
  activeJob,
  duration,
  currentTime,
  hasEncounteredEvidence,
  lastEvidenceWindow,
  attentionHUD,
  selectedSource,
  openDispatchModal,
  aiSummary,
  aiSummaryLoading,
  aiSummaryError,
  refreshAiSummary,
}) {
  const [activeTab, setActiveTab] = useState('detection');

  return (
    <div className="w-full xl:w-[30%] bg-[#0D0E13] flex flex-col shrink-0 font-mono text-xs overflow-hidden">
      <div className="flex items-center gap-1.5 p-2 border-b border-[#1E2232] shrink-0">
        <button
          onClick={() => setActiveTab('copilot')}
          className={`px-3 py-1.5 rounded-sm transition-colors flex items-center gap-1.5 uppercase font-bold text-[11px] ${
            activeTab === 'copilot'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/50'
              : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A] border border-transparent'
          }`}
        >
          <Icons.Bot className="w-3.5 h-3.5" />
          <span>AI COPILOT</span>
        </button>
        <button
          onClick={() => setActiveTab('detection')}
          className={`px-3 py-1.5 rounded-sm transition-colors flex items-center gap-1.5 uppercase font-bold text-[11px] ${
            activeTab === 'detection'
              ? 'bg-blue-600/20 text-blue-400 border border-blue-500/50'
              : 'text-slate-400 hover:text-slate-200 hover:bg-[#11131A] border border-transparent'
          }`}
        >
          <Icons.Layers className="w-3.5 h-3.5" />
          <span>DETECTION DATA</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 lg:p-6">
        {activeTab === 'detection' && (
          <AnalysisResultsPanel
            activeJob={activeJob}
            duration={duration}
            currentTime={currentTime}
            hasEncounteredEvidence={hasEncounteredEvidence}
            lastEvidenceWindow={lastEvidenceWindow}
            attentionHUD={attentionHUD}
            selectedSource={selectedSource}
            openDispatchModal={openDispatchModal}
          />
        )}

        {activeTab === 'copilot' && (
          <AiCopilotPanel
            activeJob={activeJob}
            aiSummary={aiSummary}
            aiSummaryLoading={aiSummaryLoading}
            aiSummaryError={aiSummaryError}
            refreshAiSummary={refreshAiSummary}
          />
        )}
      </div>
    </div>
  );
}
