const REQUEST_HEADER_ALLOWLIST = new Set([
  "accept",
  "content-type",
  "idempotency-key",
  "if-none-match",
  "x-request-id"
]);

const RESPONSE_HEADER_ALLOWLIST = new Set([
  "content-disposition",
  "content-type",
  "etag",
  "retry-after",
  "server-timing",
  "x-trace-id"
]);

export function allowedBackendRequestHeaders(source) {
  const headers = new Headers();
  for (const [name, value] of source.entries()) {
    if (REQUEST_HEADER_ALLOWLIST.has(name.toLowerCase())) {
      headers.set(name, value);
    }
  }
  return headers;
}

export function allowedBackendResponseHeaders(source) {
  const headers = new Headers();
  for (const [name, value] of source.entries()) {
    if (RESPONSE_HEADER_ALLOWLIST.has(name.toLowerCase())) {
      headers.set(name, value);
    }
  }
  headers.set("Cache-Control", "private, no-store");
  headers.set("Vary", "Cookie");
  return headers;
}
