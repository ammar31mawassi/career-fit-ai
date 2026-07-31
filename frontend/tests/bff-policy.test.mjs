import assert from "node:assert/strict";
import test from "node:test";

import {
  allowedBackendRequestHeaders,
  allowedBackendResponseHeaders
} from "../lib/bff-policy.mjs";

test("BFF forwards only explicit browser request headers", () => {
  const headers = allowedBackendRequestHeaders(
    new Headers({
      Accept: "application/json",
      Authorization: "Bearer attacker-controlled",
      Cookie: "session=private",
      "Idempotency-Key": "scan-123",
      "If-None-Match": '"page-etag"',
      "X-Forwarded-For": "127.0.0.1",
      "X-Request-ID": "trace-123456"
    })
  );

  assert.deepEqual(Object.fromEntries(headers.entries()), {
    accept: "application/json",
    "idempotency-key": "scan-123",
    "if-none-match": '"page-etag"',
    "x-request-id": "trace-123456"
  });
});

test("BFF exposes only stable backend response metadata", () => {
  const headers = allowedBackendResponseHeaders(
    new Headers({
      "Content-Type": "application/json",
      ETag: '"page-etag"',
      Location: "https://internal.example",
      "Set-Cookie": "private=secret",
      "X-Trace-ID": "trace-123456"
    })
  );

  assert.deepEqual(Object.fromEntries(headers.entries()), {
    "cache-control": "private, no-store",
    "content-type": "application/json",
    etag: '"page-etag"',
    vary: "Cookie",
    "x-trace-id": "trace-123456"
  });
});
