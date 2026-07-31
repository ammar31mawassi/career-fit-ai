export function safeExternalWebUrl(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}
