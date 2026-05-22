// Phase 17 EXTRACT-04 — ExtractionPreviewForm component contract.
// RED-state stub. Plan 17-06 lands the component + vitest run.
// Mirrors the frontend stub convention from Phase 15 (describe.skip + it.todo).

import { describe, it } from "vitest";

describe.skip("ExtractionPreviewForm (Plan 17-06)", () => {
  it.todo("renders the FileDropzone full-bleed in the empty state");
  it.todo("collapses the dropzone to a chip after a successful extraction");
  it.todo("fills each form field with the extracted value and confidence badge");
  it.todo("renders amber badge for per-field confidence below 0.75 (D-08)");
  it.todo("renders red badge and 'needs review' chip for per-field confidence below 0.55 (D-08)");
  it.todo("renders a 'structurally suspect' icon next to fields that failed D-33 validation");
  it.todo("hover copy on the validation icon explains the failure reason (D-34)");
  it.todo("per-field accept button locks the value and records was_edited=false");
  it.todo("per-field edit flow flips the field to user-edited and preserves original in hidden state");
  it.todo("per-field discard removes the value and clears the badge");
  it.todo("shows an inline banner when the tenant has no AICredential (D-14, D-30)");
  it.todo("shows a determinate progress bar during upload, indeterminate during extract (D-29)");
});
