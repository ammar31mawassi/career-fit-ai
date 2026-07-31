import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_BROWSER_OCR_LIMITS,
  describeBrowserOcrCoverage,
  isAbortError,
  planBrowserOcrCoverage,
  planBrowserOcrRaster,
  validateBrowserOcrFile,
  validateBrowserOcrRasterTotal
} from "../lib/browser-ocr-policy.mjs";

test("browser OCR rejects invalid or oversized files before reading them", () => {
  assert.equal(
    validateBrowserOcrFile({ name: "cv.pdf", size: 0, type: "application/pdf" }).ok,
    false
  );
  assert.match(
    validateBrowserOcrFile({
      name: "cv.pdf",
      size: DEFAULT_BROWSER_OCR_LIMITS.maxFileBytes + 1,
      type: "application/pdf"
    }).error,
    /no larger than 5 MB/
  );
  assert.equal(
    validateBrowserOcrFile({ name: "cv.txt", size: 100, type: "text/plain" }).ok,
    false
  );
  assert.equal(
    validateBrowserOcrFile({ name: "cv.pdf", size: 100, type: "" }).ok,
    true
  );
});

test("page coverage explicitly records and describes truncation", () => {
  const coverage = planBrowserOcrCoverage(12);

  assert.deepEqual(coverage, {
    totalPages: 12,
    processedPages: 8,
    omittedPages: 4,
    truncated: true
  });
  assert.equal(
    describeBrowserOcrCoverage(coverage),
    "Local OCR processed the first 8 of 12 pages. 4 later pages were not included."
  );
  assert.match(
    describeBrowserOcrCoverage(planBrowserOcrCoverage(3)),
    /all 3 of 3 pages/
  );
});

test("raster planning caps both the longest edge and page pixels before canvas allocation", () => {
  const plan = planBrowserOcrRaster(10_000, 10_000);

  assert.ok(plan.width <= DEFAULT_BROWSER_OCR_LIMITS.maxRenderEdge);
  assert.ok(plan.height <= DEFAULT_BROWSER_OCR_LIMITS.maxRenderEdge);
  assert.ok(plan.pixels <= DEFAULT_BROWSER_OCR_LIMITS.maxPagePixels);
  assert.throws(
    () => planBrowserOcrRaster(Number.POSITIVE_INFINITY, 100),
    /too large|invalid/
  );
});

test("aggregate raster policy rejects an otherwise valid set before rendering", () => {
  const belowLimit = validateBrowserOcrRasterTotal([
    { pixels: 4_000_000 },
    { pixels: 4_000_000 }
  ]);
  const aboveLimit = validateBrowserOcrRasterTotal(
    Array.from({ length: 6 }, () => ({ pixels: 4_000_000 }))
  );

  assert.equal(belowLimit.ok, true);
  assert.equal(aboveLimit.ok, false);
  assert.match(aboveLimit.error, /too much image memory/);
});

test("abort detection is narrow and stable", () => {
  assert.equal(isAbortError(new DOMException("stopped", "AbortError")), true);
  assert.equal(isAbortError(new Error("network failed")), false);
  assert.equal(isAbortError(null), false);
});
