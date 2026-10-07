/**
 * Dispatch/notification service boundary.
 *
 * The real backend has no notification mechanism at all — no
 * `/api/v1/incidents/*` or `/api/v1/notifications/*` route exists
 * (confirmed by a repo-wide grep across `backend/app/`). The previous
 * prototype's call to `/api/v1/incidents/{jobId}/notify` targeted a route
 * that has never existed; it has been removed, not pointed at a stub.
 *
 * This module makes no network call. It always returns an honest
 * "not_configured" result so the dispatch UI can render its real
 * not-configured state rather than a fabricated delivery confirmation.
 * A real WhatsApp-based notification mechanism will be integrated here
 * later, as its own separate piece of work.
 */

export interface DispatchNotificationRequest {
  jobId: string;
  responderId: string;
  message: string;
  phone: string;
}

export interface DispatchNotificationResult {
  status: "not_configured";
  reason: string;
}

/**
 * Always resolves to a "not_configured" result. No network request is
 * made — there is nothing real to call yet.
 */
export async function sendDispatchNotification(
  _request: DispatchNotificationRequest,
): Promise<DispatchNotificationResult> {
  return {
    status: "not_configured",
    reason: "Notification backend not yet integrated.",
  };
}
