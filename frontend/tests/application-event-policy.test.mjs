import assert from "node:assert/strict";
import test from "node:test";

import {
  localDateInput,
  occurredAtForLocalDate
} from "../lib/application-event-policy.mjs";

test("same-day application events use the current time before local noon", () => {
  const now = new Date(2026, 6, 31, 8, 30, 0, 0);

  assert.equal(occurredAtForLocalDate(localDateInput(now), now), now.toISOString());
});

test("same-day application events use local noon once it is in the past", () => {
  const now = new Date(2026, 6, 31, 16, 30, 0, 0);
  const localNoon = new Date(2026, 6, 31, 12, 0, 0, 0);

  assert.equal(occurredAtForLocalDate(localDateInput(now), now), localNoon.toISOString());
});

test("historical application dates preserve the selected local business date", () => {
  const now = new Date(2026, 6, 31, 8, 30, 0, 0);
  const localNoon = new Date(2026, 6, 30, 12, 0, 0, 0);

  assert.equal(occurredAtForLocalDate("2026-07-30", now), localNoon.toISOString());
});

test("application event dates reject future and impossible calendar values", () => {
  const now = new Date(2026, 6, 31, 8, 30, 0, 0);

  assert.throws(() => occurredAtForLocalDate("2026-08-01", now), /future/);
  assert.throws(() => occurredAtForLocalDate("2026-02-30", now), /real calendar date/);
  assert.throws(() => occurredAtForLocalDate("31-07-2026", now), /YYYY-MM-DD/);
});
