import { useCallback, useEffect, useState } from 'react';

/**
 * Data-fetching hook for the AI Incident Assistant tab. Owns no UI --
 * just the latest-incident-summary fetch, the eligible-responders fetch
 * (gated on having real coordinates to query with), the Grok-backed AI
 * summary fetch (powers the AI COPILOT tab), and the loading/error states
 * a view needs to render honestly.
 *
 * Deliberately does NOT fall back to simulated/fabricated data on error --
 * matches apiClient.getLatestIncidentSummary()/getEligibleResponders()/
 * getLatestIncidentAiSummary()'s own honesty contract. A failure surfaces
 * as `summaryError`/`eligibleError`/`aiSummaryError`, not as fake success.
 */
export function useIncidentAssistant(apiClient) {
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);

  const [eligibleResponders, setEligibleResponders] = useState([]);
  const [eligibleCount, setEligibleCount] = useState(0);
  const [eligibleLoading, setEligibleLoading] = useState(false);
  const [eligibleError, setEligibleError] = useState(null);

  // AI COPILOT tab state -- a real Grok (xAI)-generated incident summary,
  // or an honest deterministic fallback when Grok is unavailable. See
  // AiCopilotPanel.jsx for how this is rendered.
  const [aiSummary, setAiSummary] = useState(null);
  const [aiSummaryLoading, setAiSummaryLoading] = useState(false);
  const [aiSummaryError, setAiSummaryError] = useState(null);

  const refreshSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const data = await apiClient.getLatestIncidentSummary();
      setSummary(data);
    } catch (err) {
      setSummaryError(err.message || 'Failed to load latest incident summary.');
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [apiClient]);

  const refreshAiSummary = useCallback(async (forceRefresh = false) => {
    setAiSummaryLoading(true);
    setAiSummaryError(null);
    try {
      const data = await apiClient.getLatestIncidentAiSummary({ forceRefresh });
      setAiSummary(data);
    } catch (err) {
      setAiSummaryError(err.message || 'Failed to load AI incident summary.');
      setAiSummary(null);
    } finally {
      setAiSummaryLoading(false);
    }
  }, [apiClient]);

  const refreshEligibleResponders = useCallback(async ({ lat, lng, radius_km = 10 } = {}) => {
    if (lat == null || lng == null) {
      setEligibleResponders([]);
      setEligibleCount(0);
      setEligibleError(null);
      return;
    }
    setEligibleLoading(true);
    setEligibleError(null);
    try {
      const data = await apiClient.getEligibleResponders({ lat, lng, radius_km });
      setEligibleResponders(data.responders || []);
      setEligibleCount(data.eligible_count || 0);
    } catch (err) {
      setEligibleError(err.message || 'Failed to load eligible responders.');
      setEligibleResponders([]);
      setEligibleCount(0);
    } finally {
      setEligibleLoading(false);
    }
  }, [apiClient]);

  // Load the latest incident summary once on mount -- the tab's primary
  // content, not gated on anything else being available first.
  useEffect(() => {
    refreshSummary();
  }, [refreshSummary]);

  return {
    summary,
    summaryLoading,
    summaryError,
    refreshSummary,
    aiSummary,
    aiSummaryLoading,
    aiSummaryError,
    refreshAiSummary,
    eligibleResponders,
    eligibleCount,
    eligibleLoading,
    eligibleError,
    refreshEligibleResponders,
  };
}

export default useIncidentAssistant;
