// Phase 15 — EMAIL-07 fetch-log activity rendering tests.
// RED-state stub. Plan 06 lands vitest config + FetchActivity component.
import { describe, it } from "vitest";

describe.skip("FetchActivity (Plan 06)", () => {
  it.todo("renders three-state badges: SUCCESS_EMPTY / SUCCESS_WITH_RESULTS / FETCH_FAILED");
  it.todo("highlights row in red when status=FETCH_FAILED");
  it.todo("paginates older fetch_log entries");
  it.todo("shows reconnect prompt when 2x consecutive FETCH_FAILED detected");
});
