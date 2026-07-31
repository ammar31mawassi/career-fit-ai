import assert from "node:assert/strict";
import test from "node:test";

import {
  createKeyedOperationGate,
  createKeyedRequestPool,
  summaryInvalidatesDetail,
  withoutItemId
} from "../lib/ui-concurrency.mjs";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

test("keyed request pool shares a pending hover request with selection", async () => {
  const pending = deferred();
  let calls = 0;
  const pool = createKeyedRequestPool(async () => {
    calls += 1;
    return pending.promise;
  });

  const hoverRequest = pool.load(42);
  const selectionRequest = pool.load(42);

  assert.equal(hoverRequest, selectionRequest);
  assert.equal(calls, 1);
  pending.resolve({ id: 42 });
  assert.deepEqual(await selectionRequest, { id: 42 });
  assert.equal(pool.has(42), false);
});

test("failed pooled request is released so inspector retry starts a new request", async () => {
  let calls = 0;
  const pool = createKeyedRequestPool(async () => {
    calls += 1;
    if (calls === 1) throw new Error("temporary failure");
    return { id: 7 };
  });

  await assert.rejects(pool.load(7), /temporary failure/);
  assert.deepEqual(await pool.load(7), { id: 7 });
  assert.equal(calls, 2);
});

test("operation gate blocks duplicate item mutations but permits different cards", () => {
  const gate = createKeyedOperationGate();
  const first = gate.begin(1);
  const second = gate.begin(2);

  assert.equal(typeof first, "symbol");
  assert.equal(typeof second, "symbol");
  assert.equal(gate.begin(1), null);
  assert.equal(gate.isCurrent(1, first), true);
  assert.equal(gate.end(1, second), false);
  assert.equal(gate.end(1, first), true);
  assert.equal(typeof gate.begin(1), "symbol");
});

test("functional recommendation removals compose without resurrecting cards", () => {
  let items = [{ id: 1 }, { id: 2 }, { id: 3 }];
  const removeFirst = (current) => withoutItemId(current, 1);
  const removeSecond = (current) => withoutItemId(current, 2);

  items = removeFirst(items);
  items = removeSecond(items);

  assert.deepEqual(items, [{ id: 3 }]);
});

test("a newer matching summary invalidates full job detail", () => {
  const detail = { id: 42, updated_at: "2026-07-30T10:00:00Z" };

  assert.equal(
    summaryInvalidatesDetail(detail, { id: 42, updated_at: "2026-07-30T10:00:01Z" }),
    true
  );
  assert.equal(
    summaryInvalidatesDetail(detail, { id: 42, updated_at: "2026-07-30T10:00:00Z" }),
    false
  );
  assert.equal(
    summaryInvalidatesDetail(detail, { id: 7, updated_at: "2026-07-30T10:00:01Z" }),
    false
  );
});
