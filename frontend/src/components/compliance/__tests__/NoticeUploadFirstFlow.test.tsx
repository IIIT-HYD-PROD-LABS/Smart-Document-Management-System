// Phase 17 EXTRACT-04 / EXTRACT-05 — /notices/new upload-first flow.
// RED-state stub. Plan 17-06 lands the page rewrite + vitest config.

import { describe, it } from "vitest";

describe.skip("Notices /new upload-first flow (Plan 17-06)", () => {
  it.todo("starts with a dropzone hero, no form fields visible");
  it.todo("after drop, calls POST /api/compliance/notices/extract-preview with the file");
  it.todo("after extract-preview resolves, renders the form populated by extracted fields");
  it.todo("Save sends the accepted-fields payload alongside the file to the create endpoint");
  it.todo("low-confidence extraction shows a 'queued for review' confirmation instead of the form");
  it.todo("extraction failure (provider error) falls back to manual-fill with a non-blocking banner");
  it.todo("no AICredential → dropzone collapses, manual-fill banner sits inline, file still saves");
});
