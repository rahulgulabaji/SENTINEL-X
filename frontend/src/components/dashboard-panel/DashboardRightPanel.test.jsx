import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DashboardRightPanel from './DashboardRightPanel';

function baseProps(overrides = {}) {
  return {
    activeJob: null,
    duration: null,
    currentTime: 0,
    hasEncounteredEvidence: false,
    lastEvidenceWindow: null,
    attentionHUD: { visible: false },
    selectedSource: { location: 'Test Site' },
    openDispatchModal: vi.fn(),
    aiSummary: null,
    aiSummaryLoading: false,
    aiSummaryError: null,
    refreshAiSummary: vi.fn(),
    ...overrides,
  };
}

describe('DashboardRightPanel', () => {
  it('defaults to the DETECTION DATA tab', () => {
    render(<DashboardRightPanel {...baseProps()} />);
    // AnalysisResultsPanel's standby content renders by default.
    expect(screen.getByText('READY FOR ANALYSIS')).toBeInTheDocument();
    expect(screen.queryByText(/generating incident summary/i)).not.toBeInTheDocument();
  });

  it('switches to the AI COPILOT tab on click and fetches the summary once switched to', () => {
    const refreshAiSummary = vi.fn();
    render(<DashboardRightPanel {...baseProps({ refreshAiSummary })} />);

    fireEvent.click(screen.getByText('AI COPILOT'));

    expect(refreshAiSummary).toHaveBeenCalled();
    expect(screen.queryByText('READY FOR ANALYSIS')).not.toBeInTheDocument();
  });

  it('switching back to DETECTION DATA restores the AnalysisResultsPanel content', () => {
    render(<DashboardRightPanel {...baseProps()} />);

    fireEvent.click(screen.getByText('AI COPILOT'));
    fireEvent.click(screen.getByText('DETECTION DATA'));

    expect(screen.getByText('READY FOR ANALYSIS')).toBeInTheDocument();
  });

  it('passes activeJob/duration/currentTime through to AnalysisResultsPanel unchanged', () => {
    const activeJob = {
      jobId: 'JOB-1',
      status: 'completed',
      system: 'anomaly',
      result: { anomaly_detected: true, likely_action: 'Loitering', anomaly_probability: 0.8, action_confidence: 0.6 },
    };
    render(<DashboardRightPanel {...baseProps({ activeJob, hasEncounteredEvidence: true })} />);

    expect(screen.getByText('INCIDENT DETECTED')).toBeInTheDocument();
    expect(screen.getAllByText('Loitering').length).toBeGreaterThan(0);
  });
});
