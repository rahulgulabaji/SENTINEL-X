import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AiCopilotPanel from './AiCopilotPanel';

const SAMPLE_SUMMARY = {
  incident: { incident_id: 'inc-1', job_id: 'job-1' },
  summary: {
    headline: 'Fighting detected',
    ai_detected: { anomaly_probability: 0.9, likely_action: 'Fighting', action_confidence: 0.75 },
    location: { available: true, label: 'Gate 3, North Perimeter' },
    limitations: ['Severity/priority is not tracked by this system.'],
  },
  ai_summary_text: 'A real Grok-generated incident summary.',
  ai_summary_source: 'grok',
  ai_summary_error: null,
};

function baseProps(overrides = {}) {
  return {
    activeJob: null,
    aiSummary: null,
    aiSummaryLoading: false,
    aiSummaryError: null,
    refreshAiSummary: vi.fn(),
    ...overrides,
  };
}

describe('AiCopilotPanel', () => {
  it('fetches the AI summary once on mount', () => {
    const refreshAiSummary = vi.fn();
    render(<AiCopilotPanel {...baseProps({ refreshAiSummary })} />);

    expect(refreshAiSummary).toHaveBeenCalledTimes(1);
    expect(refreshAiSummary).toHaveBeenCalledWith(false);
  });

  it('does not fetch again just because the job is queued/processing -- only the mount fetch has fired so far', () => {
    const refreshAiSummary = vi.fn();
    render(
      <AiCopilotPanel {...baseProps({ activeJob: { jobId: 'job-1', status: 'processing' }, refreshAiSummary })} />
    );
    // The mount-fetch fires once regardless; queued/processing must not add a second call.
    expect(refreshAiSummary).toHaveBeenCalledTimes(1);
  });

  it('fetches again the instant the job completes -- same real-data moment DETECTION DATA gets its result', () => {
    const refreshAiSummary = vi.fn();
    const { rerender } = render(
      <AiCopilotPanel {...baseProps({ activeJob: { jobId: 'job-1', status: 'processing' }, refreshAiSummary })} />
    );
    expect(refreshAiSummary).toHaveBeenCalledTimes(1); // mount fetch only

    rerender(
      <AiCopilotPanel {...baseProps({ activeJob: { jobId: 'job-1', status: 'completed' }, refreshAiSummary })} />
    );
    expect(refreshAiSummary).toHaveBeenCalledTimes(2);
    expect(refreshAiSummary).toHaveBeenLastCalledWith(false);

    // Re-render with the same completed job -- must NOT trigger a third fetch.
    rerender(
      <AiCopilotPanel {...baseProps({ activeJob: { jobId: 'job-1', status: 'completed' }, refreshAiSummary })} />
    );
    expect(refreshAiSummary).toHaveBeenCalledTimes(2);

    // A new job completing -- must trigger exactly one more fetch.
    rerender(
      <AiCopilotPanel {...baseProps({ activeJob: { jobId: 'job-2', status: 'completed' }, refreshAiSummary })} />
    );
    expect(refreshAiSummary).toHaveBeenCalledTimes(3);
  });

  it('shows a loading state while the summary has not arrived yet', () => {
    render(<AiCopilotPanel {...baseProps({ aiSummaryLoading: true })} />);
    expect(screen.getByText(/generating incident summary/i)).toBeInTheDocument();
  });

  it('shows an honest error state on fetch failure, never fabricated data', () => {
    render(<AiCopilotPanel {...baseProps({ aiSummaryError: 'Backend unreachable' })} />);
    expect(screen.getByText(/summary unavailable/i)).toBeInTheDocument();
    expect(screen.getByText('Backend unreachable')).toBeInTheDocument();
  });

  it('shows the empty state when there are no incidents yet', () => {
    render(
      <AiCopilotPanel
        {...baseProps({ aiSummary: { incident: null, summary: null, ai_summary_text: null, ai_summary_source: null, ai_summary_error: null } })}
      />
    );
    expect(screen.getByText(/no incidents recorded yet/i)).toBeInTheDocument();
  });

  it('renders the real Grok summary text (fully typed) and GROK source badge', () => {
    vi.useFakeTimers();
    render(<AiCopilotPanel {...baseProps({ aiSummary: SAMPLE_SUMMARY })} />);

    // The summary text types out over time (chatbot-style reveal) --
    // advance well past its full length before asserting the complete,
    // real text is on screen. The content itself is never altered by
    // the animation, only the pace it's drawn at. act() flushes the
    // setShown state updates the setInterval callback schedules.
    act(() => {
      vi.advanceTimersByTime(SAMPLE_SUMMARY.ai_summary_text.length * 18 + 50);
    });
    vi.useRealTimers();

    expect(screen.getByText('A real Grok-generated incident summary.')).toBeInTheDocument();
    expect(screen.getByText('GROK')).toBeInTheDocument();
    expect(screen.getByText('Fighting')).toBeInTheDocument();
    expect(screen.getByText('Gate 3, North Perimeter')).toBeInTheDocument();
  });

  it('starts the typewriter reveal immediately -- first character is on screen right after mount', () => {
    vi.useFakeTimers();
    render(<AiCopilotPanel {...baseProps({ aiSummary: SAMPLE_SUMMARY })} />);

    // One tick in: not yet complete, but already showing real text --
    // this is the "feels instant, like it's typing" behavior requested.
    act(() => {
      vi.advanceTimersByTime(18);
    });
    expect(screen.getByText(/^A$/)).toBeInTheDocument();

    vi.useRealTimers();
  });

  it('renders the FALLBACK badge (never GROK) when ai_summary_source is fallback', () => {
    vi.useFakeTimers();
    const fallbackSummary = { ...SAMPLE_SUMMARY, ai_summary_source: 'fallback', ai_summary_text: 'Deterministic fallback summary.' };
    render(<AiCopilotPanel {...baseProps({ aiSummary: fallbackSummary })} />);

    act(() => {
      vi.advanceTimersByTime(fallbackSummary.ai_summary_text.length * 18 + 50);
    });
    vi.useRealTimers();

    expect(screen.getByText(/fallback summary \(ai unavailable\)/i)).toBeInTheDocument();
    expect(screen.getByText('Deterministic fallback summary.')).toBeInTheDocument();
    expect(screen.queryByText('GROK')).not.toBeInTheDocument();
  });

  it('refresh button triggers a forced refresh', () => {
    const refreshAiSummary = vi.fn();
    render(<AiCopilotPanel {...baseProps({ aiSummary: SAMPLE_SUMMARY, refreshAiSummary })} />);
    refreshAiSummary.mockClear();

    fireEvent.click(screen.getByText('REFRESH'));

    expect(refreshAiSummary).toHaveBeenCalledWith(true);
  });

  it('renders limitations exactly as returned by the backend', () => {
    render(<AiCopilotPanel {...baseProps({ aiSummary: SAMPLE_SUMMARY })} />);
    expect(screen.getByText('Severity/priority is not tracked by this system.')).toBeInTheDocument();
  });
});
