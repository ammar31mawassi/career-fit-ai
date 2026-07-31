import assert from "node:assert/strict";
import test from "node:test";
import { safeExternalWebUrl } from "../lib/url-policy.mjs";

test("external links allow only absolute HTTP and HTTPS destinations", () => {
  assert.equal(safeExternalWebUrl("https://jobs.example/role"), "https://jobs.example/role");
  assert.equal(safeExternalWebUrl("http://jobs.example/role"), "http://jobs.example/role");
  assert.equal(safeExternalWebUrl("javascript:alert(1)"), null);
  assert.equal(safeExternalWebUrl("data:text/html,unsafe"), null);
  assert.equal(safeExternalWebUrl("//attacker.example/role"), null);
  assert.equal(safeExternalWebUrl("/relative"), null);
});
