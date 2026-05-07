// Phase 15 — EMAIL-01 frontend OAuth handoff tests.
// RED-state stub. Plan 06 lands vitest config + ConnectGmailButton component.
import { describe, it } from "vitest";

describe.skip("ConnectGmailButton (Plan 06)", () => {
  it.todo("renders 'Connect Gmail' when no credential exists");
  it.todo("redirects to /api/email/gmail/oauth/authorize on click");
  it.todo("displays connected status when credential.status='active'");
  it.todo("shows reconnect banner when credential.status='REVOKED'");
});
