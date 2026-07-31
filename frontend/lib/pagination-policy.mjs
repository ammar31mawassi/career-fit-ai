/**
 * Build the stable-snapshot pagination contract used by the saved-job list.
 *
 * @param {{ cursor?: string; limit?: number; watermark?: string | null }} options
 */
export function jobSummaryPageParameters({
  cursor = "",
  limit = 30,
  watermark = null
} = {}) {
  const parameters = new URLSearchParams({ limit: String(limit) });
  if (cursor) parameters.set("cursor", cursor);
  if (watermark) parameters.set("watermark", watermark);
  return parameters;
}
