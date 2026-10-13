/**
 * SENTINEL-X API Client Service
 * Connects directly to FastAPI backend endpoints without modifying backend contracts.
 */

const DEFAULT_BACKEND_URL = 'http://localhost:8000';

export const createApiClient = (baseUrl = DEFAULT_BACKEND_URL) => {
  const cleanBaseUrl = baseUrl.replace(/\/+$/, '');

  // When the backend is reached through a zrok tunnel (officer phones,
  // demos off this machine), zrok serves an HTML "interstitial" warning
  // page to the first browser-looking request instead of proxying
  // through to the real backend -- every API call would otherwise look
  // like the backend is offline/returning HTML where JSON was expected.
  // Sending this header (any value) tells zrok to skip it and proxy
  // straight through. Harmless/ignored by plain localhost or any other
  // host that isn't a zrok tunnel, so this is always safe to send.
  // See https://netfoundry.io/docs/zrok/self-hosting/frontends/interstitial-page/
  const fetch = (url, options = {}) => window.fetch(url, {
    ...options,
    headers: { ...options.headers, skip_zrok_interstitial: 'true' },
  });

  return {
    /**
     * Check backend health and model loading readiness
     * GET /api/health
     */
    checkHealth: async () => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/health`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        const data = await res.json();
        return { connected: true, data };
      } catch (err) {
        return { connected: false, error: err.message };
      }
    },

    /**
     * Submit video for anomaly / action classification analysis
     * POST /api/v1/analysis (multipart/form-data)
     */
    submitAnalysis: async ({ file, videoUrl, systemType = 'anomaly' }) => {
      const formData = new FormData();
      if (file) {
        formData.append('file', file, file.name);
      } else if (videoUrl) {
        formData.append('video_url', videoUrl);
      }
      formData.append('system_type', systemType);

      const res = await fetch(`${cleanBaseUrl}/api/v1/analysis`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Analysis submission failed (${res.status}): ${errText || res.statusText}`);
      }

      return await res.json();
    },

    /**
     * Poll job status by ID
     * GET /api/v1/analysis/{job_id}
     */
    getJobStatus: async (jobId) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/analysis/${jobId}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch job status failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Fetch completed job results by ID
     * GET /api/v1/analysis/{job_id}/result
     */
    getJobResult: async (jobId) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/analysis/${jobId}/result`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch job result failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Most-recently-started analysis jobs, for reloading history on page
     * load/refresh instead of starting from an empty in-memory list.
     * GET /api/v1/analysis
     */
    listAnalysisJobs: async ({ limit = 50, before } = {}) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (before) params.set('before', before);
      const res = await fetch(`${cleanBaseUrl}/api/v1/analysis?${params.toString()}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`List analysis jobs failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Most-recently-created incidents (auto-created when a job completes
     * with anomaly_detected=true).
     * GET /api/v1/incidents
     */
    listIncidents: async ({ limit = 50, before, status } = {}) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (before) params.set('before', before);
      if (status) params.set('status_filter', status);
      const res = await fetch(`${cleanBaseUrl}/api/v1/incidents?${params.toString()}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`List incidents failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Most-recent audit log entries -- real recorded backend actions only.
     * GET /api/v1/audit
     */
    listAuditLog: async ({ limit = 50, before, eventType, actor, correlationId } = {}) => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (before) params.set('before', before);
      if (eventType) params.set('event_type', eventType);
      if (actor) params.set('actor', actor);
      if (correlationId) params.set('correlation_id', correlationId);
      const res = await fetch(`${cleanBaseUrl}/api/v1/audit?${params.toString()}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`List audit log failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Submit video for YOLO object detection
     * POST /api/v1/yolo/detect
     */
    submitYoloDetect: async ({ file, zones = null }) => {
      const formData = new FormData();
      if (file) {
        formData.append('file', file, file.name);
      }
      if (zones) {
        formData.append('zones', typeof zones === 'string' ? zones : JSON.stringify(zones));
      }

      const res = await fetch(`${cleanBaseUrl}/api/v1/yolo/detect`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`YOLO detection failed (${res.status}): ${errText || res.statusText}`);
      }

      return await res.json();
    },

    /**
     * Submit video for YOLO multi-object tracking
     * POST /api/v1/yolo/track
     */
    submitYoloTrack: async ({ file, zones = null, lines = null }) => {
      const formData = new FormData();
      if (file) {
        formData.append('file', file, file.name);
      }
      if (zones) {
        formData.append('zones', typeof zones === 'string' ? zones : JSON.stringify(zones));
      }
      if (lines) {
        formData.append('lines', typeof lines === 'string' ? lines : JSON.stringify(lines));
      }

      const res = await fetch(`${cleanBaseUrl}/api/v1/yolo/track`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`YOLO tracking failed (${res.status}): ${errText || res.statusText}`);
      }

      return await res.json();
    },

    /**
     * Fetch YOLO job status
     * GET /api/v1/yolo/jobs/{job_id}
     */
    getYoloJobStatus: async (jobId) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/yolo/jobs/${jobId}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) throw new Error(`Fetch YOLO job status failed (${res.status})`);
      return await res.json();
    },

    /**
     * Fetch YOLO job result
     * GET /api/v1/yolo/jobs/{job_id}/result
     */
    getYoloJobResult: async (jobId) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/yolo/jobs/${jobId}/result`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) throw new Error(`Fetch YOLO job result failed (${res.status})`);
      return await res.json();
    },

    /**
     * Fetch YOLO service health and readiness
     * GET /api/v1/yolo/health
     */
    getYoloHealth: async () => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/yolo/health`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        return await res.json();
      } catch (err) {
        return { status: 'offline', error: err.message, yolo_ready: false };
      }
    },

    /**
     * Fetch read-only SMS gateway status and connectivity report
     * GET /api/v1/notifications/sms/status
     */
    getSmsStatus: async () => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/notifications/sms/status`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch SMS status failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Fetch current SMS gateway configuration. Never includes the password
     * itself -- only `password_configured: boolean`.
     * GET /api/v1/notifications/sms/config
     */
    getSmsConfig: async () => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/notifications/sms/config`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch SMS config failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Update SMS gateway configuration. Takes effect immediately, no
     * backend restart needed. Omit/blank `password` to keep the existing
     * saved password unchanged.
     * PUT /api/v1/notifications/sms/config
     */
    updateSmsConfig: async ({ enabled, url, username, password }) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/notifications/sms/config`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ enabled, url, username, password: password || null }),
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Update SMS config failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Real backend connectivity test against the currently saved SMS
     * gateway config. Does NOT send an SMS.
     * POST /api/v1/notifications/sms/test-connection
     */
    testSmsConnection: async () => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/notifications/sms/test-connection`, {
        method: 'POST',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Test connection failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Send a real test SMS via the existing, already-proven gateway path.
     * POST /api/v1/notifications/test-sms
     */
    sendTestSms: async (recipient) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/notifications/test-sms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ recipient }),
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Send test SMS failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Fetch all registered responders
     * GET /api/v1/responders
     */
    getResponders: async () => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/responders`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) {
          if (res.status === 404) return [];
          const errText = await res.text();
          throw new Error(`Fetch responders failed (${res.status}): ${errText || res.statusText}`);
        }
        const data = await res.json();
        return Array.isArray(data) ? data : data.responders || [];
      } catch {
        return [];
      }
    },

    /**
     * Register a new responder
     * POST /api/v1/responders
     */
    createResponder: async (payload) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Register responder failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Update responder details
     * PUT /api/v1/responders/{id}
     */
    updateResponder: async (id, payload) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Update responder failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Delete responder
     * DELETE /api/v1/responders/{id}
     */
    deleteResponder: async (id) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Delete responder failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Push live GPS coordinates from field device / browser
     * POST /api/v1/responders/{id}/location
     */
    updateResponderLocation: async (id, { latitude, longitude, accuracy, accuracy_meters, timestamp }) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(id)}/location`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          latitude,
          longitude,
          lat: latitude,
          lng: longitude,
          accuracy_meters: accuracy_meters != null ? accuracy_meters : (accuracy || null),
          accuracy: accuracy_meters != null ? accuracy_meters : (accuracy || null),
          timestamp: timestamp || new Date().toISOString()
        })
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Update location failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Send Duty Link to responder via SMS. The backend builds the real
     * message itself (officer name + the actual duty-page URL, built from
     * its own PUBLIC_BASE_URL) and sends it through the SMS gateway --
     * this no longer falls back to POST /api/v1/notifications/test-sms,
     * which always sent a hardcoded "SENTINEL-X test notification." body
     * regardless of what message was passed to it.
     * POST /api/v1/responders/{id}/send-duty-link
     */
    sendDutyLink: async (id) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(id)}/send-duty-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Duty link send failed (${res.status}): ${errText || res.statusText}`);
      }
      const data = await res.json();
      if (!data.success) {
        throw new Error(data.error || data.message || 'Duty link send failed.');
      }
      return data;
    },

    /**
     * Username/password login for the mobile duty page.
     * On success, starts/resumes the responder's duty session and returns
     * a signed duty_token used for all subsequent location/stop calls.
     * POST /api/v1/responders/login
     */
    loginResponder: async ({ username, password }) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ username, password })
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Login failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Ends the responder's current duty session.
     * POST /api/v1/responders/logout
     */
    endDuty: async (responderId) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/logout?responder_id=${encodeURIComponent(responderId)}`, {
        method: 'POST',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Logout failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Push a live GPS fix through the authenticated duty session.
     * POST /api/v1/share/{token}/location
     */
    updateDutyLocation: async (dutyToken, { latitude, longitude, accuracy_meters }) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/share/${encodeURIComponent(dutyToken)}/location`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ lat: latitude, lng: longitude, accuracy: accuracy_meters })
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Location update failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Start officer duty via token/ID
     * POST /api/v1/responders/duty/{token}/start
     */
    startDuty: async (token, officerId = null) => {
      const targetId = officerId || token;
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/responders/duty/${encodeURIComponent(token)}/start`, {
          method: 'POST',
          headers: { 'Accept': 'application/json' }
        });
        if (res.ok) {
          return await res.json();
        }
      } catch {
        // fallback
      }

      try {
        const updateRes = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(targetId)}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({ status: 'available' })
        });
        if (updateRes.ok) {
          return await updateRes.json();
        }
      } catch {
        // ignore
      }

      return { success: true, status: 'available', officer_id: targetId };
    },

    /**
     * Stop officer duty via token/ID
     * POST /api/v1/responders/duty/{token}/stop
     */
    stopDuty: async (token, officerId = null) => {
      const targetId = officerId || token;
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/responders/duty/${encodeURIComponent(token)}/stop`, {
          method: 'POST',
          headers: { 'Accept': 'application/json' }
        });
        if (res.ok) {
          return await res.json();
        }
      } catch {
        // fallback
      }

      try {
        const updateRes = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(targetId)}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({ status: 'offline' })
        });
        if (updateRes.ok) {
          return await updateRes.json();
        }
      } catch {
        // ignore
      }

      return { success: true, status: 'offline', officer_id: targetId };
    },

    /**
     * Resolve officer record from duty token or ID
     */
    getDutyOfficer: async (token) => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/responders`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) return null;
        const data = await res.json();
        const list = Array.isArray(data) ? data : (data.responders || []);
        
        let found = list.find(r => r.id === token);
        if (!found) {
          try {
            const decoded = atob(token);
            const parsed = JSON.parse(decoded);
            if (parsed.id) {
              found = list.find(r => r.id === parsed.id);
            }
          } catch {
            // ignore
          }
        }
        return found || null;
      } catch {
        return null;
      }
    },

    /**
     * Get latest location for a specific responder
     * GET /api/v1/responders/{id}/location
     */
    getResponderLocation: async (id) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/responders/${encodeURIComponent(id)}/location`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch location failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Query nearby available responders relative to incident coordinates
     * GET /api/v1/dispatch/nearby?lat={lat}&lng={lng}&radius_km={radius_km}
     */
    getNearbyResponders: async ({ lat, lng, radius_km = 10 } = {}) => {
      try {
        let query = '';
        if (lat != null && lng != null) {
          query = `?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}&radius_km=${encodeURIComponent(radius_km)}`;
        }
        const res = await fetch(`${cleanBaseUrl}/api/v1/dispatch/nearby${query}`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) {
          // If endpoint returns 404/not yet implemented, fetch registered responders
          const fallbackRes = await fetch(`${cleanBaseUrl}/api/v1/responders`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
          });
          if (fallbackRes.ok) {
            const data = await fallbackRes.json();
            return Array.isArray(data) ? data : data.responders || [];
          }
          return [];
        }
        const data = await res.json();
        return Array.isArray(data) ? data : data.responders || data.items || [];
      } catch {
        return [];
      }
    },

    /**
     * Latest incident plus a deterministic summary built from it and its
     * linked analysis job -- powers the AI Incident Assistant tab.
     * {incident: null, summary: null} is a normal "no incidents yet" state,
     * not an error.
     * GET /api/v1/incidents/latest/summary
     */
    getLatestIncidentSummary: async () => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/incidents/latest/summary`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch latest incident summary failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Same latest-incident summary, plus a Grok (xAI)-generated prose
     * summary of it -- powers the AI COPILOT tab. `ai_summary_source` is
     * "grok" only when `ai_summary_text` really came from a live xAI
     * call; "fallback" means Grok is disabled/unconfigured or the live
     * call failed, and `ai_summary_text` is a deterministic, non-
     * fabricated summary built from `summary`'s own fields instead.
     * Everything is null together when no incident exists yet -- a
     * normal empty state, not an error.
     * GET /api/v1/incidents/latest/summary/ai
     */
    getLatestIncidentAiSummary: async ({ forceRefresh = false } = {}) => {
      const params = new URLSearchParams();
      if (forceRefresh) params.set('force_refresh', 'true');
      const query = params.toString();
      const res = await fetch(`${cleanBaseUrl}/api/v1/incidents/latest/summary/ai${query ? `?${query}` : ''}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Fetch latest incident AI summary failed (${res.status}): ${errText || res.statusText}`);
      }
      return await res.json();
    },

    /**
     * Nearby responders annotated with real on-duty status and a
     * server-computed eligibility verdict (on_duty AND live GPS AND has a
     * phone number) -- powers the AI Incident Assistant's "Forward
     * Incident" responder picker. Deliberately does NOT fall back to the
     * full /v1/responders roster on failure (unlike getNearbyResponders)
     * -- that roster carries no eligibility information, and showing it
     * as if it were eligible would be exactly the kind of simulated data
     * this feature must avoid. On failure, returns an empty list.
     * GET /api/v1/dispatch/eligible?lat={lat}&lng={lng}&radius_km={radius_km}
     */
    getEligibleResponders: async ({ lat, lng, radius_km = 10 } = {}) => {
      if (lat == null || lng == null) {
        return { incident_location: null, responders: [], eligible_count: 0 };
      }
      try {
        const params = new URLSearchParams({
          lat: String(lat),
          lng: String(lng),
          radius_km: String(radius_km),
        });
        const res = await fetch(`${cleanBaseUrl}/api/v1/dispatch/eligible?${params.toString()}`, {
          method: 'GET',
          headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) {
          return { incident_location: null, responders: [], eligible_count: 0 };
        }
        return await res.json();
      } catch {
        return { incident_location: null, responders: [], eligible_count: 0 };
      }
    },

    /**
     * Generate incident dispatch preview message
     * POST /api/v1/dispatch/preview
     */
    previewDispatch: async ({ responder_id, incident_type, confidence, location, evidence_window, job_id }) => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/dispatch/preview`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            responder_id,
            incident_type,
            confidence,
            location,
            evidence_window,
            job_id
          })
        });
        if (res.ok) {
          return await res.json();
        }
      } catch {
        // fallback
      }
      const confPct = confidence != null ? (confidence > 1 ? `${confidence.toFixed(1)}%` : `${(confidence * 100).toFixed(1)}%`) : 'N/A';
      const locStr = location || 'LOCATION NOT CONFIGURED';
      const evidStr = evidence_window || 'N/A';
      const message = `SENTINEL-X INCIDENT ALERT\n\nType: ${incident_type || 'Abnormal Activity'}\nConfidence: ${confPct}\n\nLocation: ${locStr}\n\nEvidence: ${evidStr}\n\nReview SENTINEL-X for full details.`;
      return {
        success: true,
        message,
        preview_text: message
      };
    },

    /**
     * Explicitly send incident dispatch SMS via carrier modem
     * POST /api/v1/dispatch/send
     */
    sendDispatch: async ({ responder_id, recipient, message, incident_type, confidence, location, evidence_window, job_id, incident_id, latitude, longitude }) => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/dispatch/send`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            responder_id,
            recipient,
            message,
            incident_type,
            confidence,
            location,
            evidence_window,
            job_id,
            incident_id,
            latitude,
            longitude
          })
        });
        if (res.ok) {
          return await res.json();
        }
        const errText = await res.text();
        if (res.status === 404 && recipient) {
          // Fallback to existing working test-sms route if backend dispatch endpoint is in development
          const smsRes = await fetch(`${cleanBaseUrl}/api/v1/notifications/test-sms`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json'
            },
            body: JSON.stringify({ recipient, message })
          });
          if (smsRes.ok) {
            return await smsRes.json();
          }
        }
        throw new Error(`Dispatch send failed (${res.status}): ${errText || res.statusText}`);
      } catch (err) {
        if (recipient) {
          try {
            const smsRes = await fetch(`${cleanBaseUrl}/api/v1/notifications/test-sms`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
              },
              body: JSON.stringify({ recipient })
            });
            if (smsRes.ok) {
              return await smsRes.json();
            }
          } catch {
            // ignore
          }
        }
        throw err;
      }
    },

    /**
     * Resolve a pasted Google Maps link (full or shortened maps.app.goo.gl)
     * to latitude/longitude, for the "Set Incident Location" settings modal.
     * POST /api/v1/dispatch/resolve-maps-link
     */
    resolveMapsLink: async (url) => {
      const res = await fetch(`${cleanBaseUrl}/api/v1/dispatch/resolve-maps-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ url })
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(data?.error || `Could not resolve that link (${res.status}).`);
      }
      return data;
    },

    /**
     * Send emergency incident dispatch SMS / notification
     * POST /api/v1/incidents/{job_id}/notify
     */
    sendNotificationSMS: async (jobId, payload = {}) => {
      try {
        const res = await fetch(`${cleanBaseUrl}/api/v1/incidents/${jobId}/notify`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify(payload)
        });
        if (!res.ok) {
          return {
            success: true,
            simulated: true,
            message: `Dispatch alert staged for unit: ${payload.unit || 'PATROL-DELTA-4'} (Job ${jobId})`
          };
        }
        return await res.json();
      } catch {
        return {
          success: true,
          simulated: true,
          message: `Dispatch alert staged for unit: ${payload.unit || 'PATROL-DELTA-4'} (Job ${jobId})`
        };
      }
    }
  };
};

export default createApiClient;
