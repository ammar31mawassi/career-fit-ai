import assert from "node:assert/strict";
import test from "node:test";

import { jobSummaryPageParameters } from "../lib/pagination-policy.mjs";

test("first job-summary page omits cursor and watermark", () => {
  const parameters = jobSummaryPageParameters({ limit: 50 });

  assert.equal(parameters.toString(), "limit=50");
});

test("load-more preserves the bootstrap snapshot watermark", () => {
  const parameters = jobSummaryPageParameters({
    cursor: "2026-07-30T12:00:00Z|42",
    limit: 30,
    watermark: "2026-07-30T12:00:00.000Z"
  });

  assert.equal(parameters.get("cursor"), "2026-07-30T12:00:00Z|42");
  assert.equal(parameters.get("limit"), "30");
  assert.equal(parameters.get("watermark"), "2026-07-30T12:00:00.000Z");
});
