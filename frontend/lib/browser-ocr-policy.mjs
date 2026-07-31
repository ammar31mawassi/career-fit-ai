export const DEFAULT_BROWSER_OCR_LIMITS = Object.freeze({
  maxFileBytes: 5 * 1024 * 1024,
  maxPages: 8,
  maxRenderEdge: 2200,
  maxPagePixels: 4_000_000,
  maxTotalPixels: 20_000_000,
  renderScale: 2
});

/**
 * @param {{ name?: string, size?: number, type?: string }} file
 * @param {typeof DEFAULT_BROWSER_OCR_LIMITS} [limits]
 */
export function validateBrowserOcrFile(file, limits = DEFAULT_BROWSER_OCR_LIMITS) {
  const size = Number(file?.size);
  const name = String(file?.name || "");
  const type = String(file?.type || "").toLowerCase();
  if (!Number.isFinite(size) || size <= 0) {
    return { ok: false, error: "Choose a non-empty PDF." };
  }
  if (size > limits.maxFileBytes) {
    return {
      ok: false,
      error: `This PDF is too large for local OCR. Choose a file no larger than ${formatBytes(limits.maxFileBytes)}.`
    };
  }
  if (!name.toLowerCase().endsWith(".pdf")) {
    return { ok: false, error: "Local OCR only supports PDF files." };
  }
  if (type && type !== "application/pdf" && type !== "application/octet-stream") {
    return { ok: false, error: "Local OCR only supports PDF files." };
  }
  return { ok: true, error: "" };
}

/**
 * @param {number} totalPages
 * @param {typeof DEFAULT_BROWSER_OCR_LIMITS} [limits]
 */
export function planBrowserOcrCoverage(totalPages, limits = DEFAULT_BROWSER_OCR_LIMITS) {
  if (!Number.isSafeInteger(totalPages) || totalPages <= 0) {
    throw new Error("This PDF does not contain any readable pages.");
  }
  const processedPages = Math.min(totalPages, limits.maxPages);
  return {
    totalPages,
    processedPages,
    omittedPages: totalPages - processedPages,
    truncated: totalPages > processedPages
  };
}

/**
 * Calculate a bounded render plan without allocating a canvas.
 *
 * @param {number} sourceWidth
 * @param {number} sourceHeight
 * @param {typeof DEFAULT_BROWSER_OCR_LIMITS} [limits]
 */
export function planBrowserOcrRaster(
  sourceWidth,
  sourceHeight,
  limits = DEFAULT_BROWSER_OCR_LIMITS
) {
  if (
    !Number.isFinite(sourceWidth)
    || !Number.isFinite(sourceHeight)
    || sourceWidth <= 0
    || sourceHeight <= 0
  ) {
    throw new Error("A PDF page has invalid dimensions and cannot be rendered safely.");
  }

  const requestedWidth = sourceWidth * limits.renderScale;
  const requestedHeight = sourceHeight * limits.renderScale;
  const requestedPixels = requestedWidth * requestedHeight;
  if (
    !Number.isFinite(requestedWidth)
    || !Number.isFinite(requestedHeight)
    || !Number.isFinite(requestedPixels)
  ) {
    throw new Error("A PDF page is too large to render safely.");
  }

  const edgeRatio = Math.min(
    1,
    limits.maxRenderEdge / Math.max(requestedWidth, requestedHeight)
  );
  const pixelRatio = Math.min(1, Math.sqrt(limits.maxPagePixels / requestedPixels));
  const appliedRatio = Math.min(edgeRatio, pixelRatio);
  const width = Math.max(1, Math.floor(requestedWidth * appliedRatio));
  const height = Math.max(1, Math.floor(requestedHeight * appliedRatio));
  const pixels = width * height;
  if (
    width > limits.maxRenderEdge
    || height > limits.maxRenderEdge
    || pixels > limits.maxPagePixels
  ) {
    throw new Error("A PDF page exceeds the local OCR render limit.");
  }
  return {
    width,
    height,
    pixels,
    viewportScale: limits.renderScale * appliedRatio
  };
}

/**
 * @param {Array<{ pixels: number }>} plans
 * @param {typeof DEFAULT_BROWSER_OCR_LIMITS} [limits]
 */
export function validateBrowserOcrRasterTotal(
  plans,
  limits = DEFAULT_BROWSER_OCR_LIMITS
) {
  const totalPixels = plans.reduce((total, plan) => total + plan.pixels, 0);
  if (!Number.isSafeInteger(totalPixels) || totalPixels > limits.maxTotalPixels) {
    return {
      ok: false,
      totalPixels,
      error: "This PDF needs too much image memory for safe local OCR. Try a smaller or text-based PDF."
    };
  }
  return { ok: true, totalPixels, error: "" };
}

/**
 * @param {{ processedPages: number, totalPages: number, omittedPages: number, truncated: boolean }} coverage
 */
export function describeBrowserOcrCoverage(coverage) {
  if (coverage.truncated) {
    return `Local OCR processed the first ${coverage.processedPages} of ${coverage.totalPages} pages. ${coverage.omittedPages} later page${coverage.omittedPages === 1 ? " was" : "s were"} not included.`;
  }
  return `Local OCR processed all ${coverage.processedPages} of ${coverage.totalPages} pages.`;
}

/** @param {unknown} error */
export function isAbortError(error) {
  return Boolean(
    error
    && typeof error === "object"
    && "name" in error
    && error.name === "AbortError"
  );
}

function formatBytes(bytes) {
  const mebibytes = bytes / (1024 * 1024);
  return `${Number.isInteger(mebibytes) ? mebibytes : mebibytes.toFixed(1)} MB`;
}
