import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useIncidentAssistant } from './useIncidentAssistant';

function mockApiClient(overrides = {}) {
  return {
    getLatestIncidentSummary: vi.fn().mockResolvedValue({ incident: null, summary: null }),
    getLatestIncidentAiSummary: vi.fn().mockResolvedValue({
      incident: null,
      summary: null,
      ai_summary_text: null,
      ai_summary_source: null,
      ai_summary_error: null,
    }),
    getEligibleResponders: vi.fn().mockResolvedValue({ incident_location: null, responders: [], eligible_count: 0 }),
    ...overrides,
  };
}

describe('useIncidentAssistant', () => {
  it('fetches the latest incident summary on mount', async () => {
    const summaryPayload = { incident: { incident_id: 'inc-1' }, summary: { headline: 'Test' } };
    const apiClient = mockApiClient({
      getLatestIncidentSummary: vi.fn().mockResolvedValue(summaryPayload),
    });

    const { result } = renderHook(() => useIncidentAssistant(apiClient));

    expect(result.current.summaryLoading).toBe(true);
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    expect(apiClient.getLatestIncidentSummary).toHaveBeenCalledTimes(1);
    expect(result.current.summary).toEqual(summaryPayload);
    expect(result.current.summaryError).toBeNull();
  });

  it('surfaces a summary fetch error without fabricating data', async () => {
    const apiClient = mockApiClient({
      getLatestIncidentSummary: vi.fn().mockRejectedValue(new Error('Network down')),
    });

    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    expect(result.current.summary).toBeNull();
    expect(result.current.summaryError).toBe('Network down');
  });

  it('does not call getEligibleResponders when coordinates are missing', async () => {
    const apiClient = mockApiClient();
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshEligibleResponders({ lat: null, lng: null });
    });

    expect(apiClient.getEligibleResponders).not.toHaveBeenCalled();
    expect(result.current.eligibleResponders).toEqual([]);
    expect(result.current.eligibleCount).toBe(0);
  });

  it('fetches eligible responders with real coordinates and stores the real count', async () => {
    const responders = [{ id: 'r1', name: 'Officer Rao', eligible: true }];
    const apiClient = mockApiClient({
      getEligibleResponders: vi.fn().mockResolvedValue({ incident_location: { lat: 16.7, lng: 74.2 }, responders, eligible_count: 1 }),
    });
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshEligibleResponders({ lat: 16.7, lng: 74.2, radius_km: 25 });
    });

    expect(apiClient.getEligibleResponders).toHaveBeenCalledWith({ lat: 16.7, lng: 74.2, radius_km: 25 });
    expect(result.current.eligibleResponders).toEqual(responders);
    expect(result.current.eligibleCount).toBe(1);
    expect(result.current.eligibleError).toBeNull();
  });

  it('surfaces an eligible-responders fetch error without falling back to fake data', async () => {
    const apiClient = mockApiClient({
      getEligibleResponders: vi.fn().mockRejectedValue(new Error('Gateway timeout')),
    });
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshEligibleResponders({ lat: 16.7, lng: 74.2 });
    });

    expect(result.current.eligibleResponders).toEqual([]);
    expect(result.current.eligibleCount).toBe(0);
    expect(result.current.eligibleError).toBe('Gateway timeout');
  });

  it('refreshSummary can be called again manually and re-fetches', async () => {
    const apiClient = mockApiClient();
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshSummary();
    });

    expect(apiClient.getLatestIncidentSummary).toHaveBeenCalledTimes(2);
  });

  it('does not fetch the AI summary on mount -- only on explicit refreshAiSummary call', async () => {
    const apiClient = mockApiClient();
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    expect(apiClient.getLatestIncidentAiSummary).not.toHaveBeenCalled();
    expect(result.current.aiSummary).toBeNull();
  });

  it('refreshAiSummary fetches and stores the real AI summary payload', async () => {
    const payload = {
      incident: { incident_id: 'inc-1' },
      summary: { headline: 'Test' },
      ai_summary_text: 'A real Grok summary.',
      ai_summary_source: 'grok',
      ai_summary_error: null,
    };
    const apiClient = mockApiClient({
      getLatestIncidentAiSummary: vi.fn().mockResolvedValue(payload),
    });
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshAiSummary();
    });

    expect(apiClient.getLatestIncidentAiSummary).toHaveBeenCalledWith({ forceRefresh: false });
    expect(result.current.aiSummary).toEqual(payload);
    expect(result.current.aiSummaryError).toBeNull();
  });

  it('refreshAiSummary(true) passes forceRefresh through to the API client', async () => {
    const apiClient = mockApiClient();
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshAiSummary(true);
    });

    expect(apiClient.getLatestIncidentAiSummary).toHaveBeenCalledWith({ forceRefresh: true });
  });

  it('surfaces an AI summary fetch error without fabricating data', async () => {
    const apiClient = mockApiClient({
      getLatestIncidentAiSummary: vi.fn().mockRejectedValue(new Error('AI backend down')),
    });
    const { result } = renderHook(() => useIncidentAssistant(apiClient));
    await waitFor(() => expect(result.current.summaryLoading).toBe(false));

    await act(async () => {
      await result.current.refreshAiSummary();
    });

    expect(result.current.aiSummary).toBeNull();
    expect(result.current.aiSummaryError).toBe('AI backend down');
  });
});
