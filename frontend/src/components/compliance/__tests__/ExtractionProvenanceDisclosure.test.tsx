// Phase 17 EXTRACT-04 — extraction provenance disclosure on notice detail.
// RED-state stub. Plan 17-06 lands the disclosure inside NoticeAISection.

import { describe, it } from "vitest";

describe.skip("ExtractionProvenanceDisclosure (Plan 17-06)", () => {
  it.todo("collapsed by default; expands to show provider, model, average confidence");
  it.todo("lists each field with auto-applied vs accepted-after-edit vs manual indicator");
  it.todo("each row links to the audit_log row id that recorded its acceptance (D-17)");
  it.todo("shows extraction_status='failed' state with retry CTA gated by NOTICE_AI_EXTRACT");
});
