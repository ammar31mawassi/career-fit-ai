import assert from "node:assert/strict";
import test from "node:test";

import {
  isAllowedSameOriginRequest,
  safePostLoginPath,
  safeSameOriginRedirect
} from "../lib/auth-policy.mjs";

test("callback redirect keeps a same-origin path, query, and fragment", () => {
  const target = safeSameOriginRedirect(
    "https://careerfit.example/auth/callback?code=secret",
    "/discover?page=2#recommended"
  );

  assert.equal(target.href, "https://careerfit.example/discover?page=2#recommended");
});

for (const candidate of [
  "https://attacker.example/steal",
  "//attacker.example/steal",
  "/\\attacker.example/steal",
  "\\\\attacker.example\\steal",
  "discover"
]) {
  test(`callback redirect rejects unsafe destination ${JSON.stringify(candidate)}`, () => {
    const target = safeSameOriginRedirect(
      "https://careerfit.example/auth/callback?code=secret",
      candidate
    );

    assert.equal(target.href, "https://careerfit.example/");
  });
}

test("post-login redirect preserves only known private workspace paths", () => {
  const requestUrl = "https://careerfit.example/login?next=%2Fdiscover";

  assert.equal(safePostLoginPath(requestUrl, "/discover?job=42"), "/discover?job=42");
  assert.equal(safePostLoginPath(requestUrl, "/profile#sources"), "/profile#sources");
  assert.equal(safePostLoginPath(requestUrl, "/backend/api/account/export"), "/");
  assert.equal(safePostLoginPath(requestUrl, "/auth/logout"), "/");
  assert.equal(safePostLoginPath(requestUrl, "//attacker.example/steal"), "/");
});

test("signup intent requires an allowed same-origin Origin header", () => {
  const requestUrl = "https://careerfit.example/auth/signup";

  assert.equal(
    isAllowedSameOriginRequest(requestUrl, "https://careerfit.example", undefined),
    true
  );
  assert.equal(
    isAllowedSameOriginRequest(
      "https://deployment-host.example/auth/signup",
      "https://careerfit.example",
      "https://careerfit.example"
    ),
    true
  );
  assert.equal(
    isAllowedSameOriginRequest(requestUrl, "https://attacker.example", undefined),
    false
  );
  assert.equal(isAllowedSameOriginRequest(requestUrl, null, undefined), false);
});
