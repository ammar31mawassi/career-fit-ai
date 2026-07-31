/**
 * Share one pending request per key and release it after either success or failure.
 *
 * @template K, V
 * @param {(key: K) => Promise<V>} loader
 */
export function createKeyedRequestPool(loader) {
  const pending = new Map();

  return {
    /** @param {K} key */
    load(key) {
      const existing = pending.get(key);
      if (existing) return existing;

      let request;
      try {
        request = Promise.resolve(loader(key));
      } catch (error) {
        request = Promise.reject(error);
      }
      pending.set(key, request);
      const release = () => {
        if (pending.get(key) === request) pending.delete(key);
      };
      request.then(release, release);
      return request;
    },
    /** @param {K} key */
    has(key) {
      return pending.has(key);
    }
  };
}

/**
 * Prevent duplicate operations for one key while allowing unrelated keys to proceed.
 *
 * @template K
 */
export function createKeyedOperationGate() {
  const active = new Map();

  return {
    /** @param {K} key */
    begin(key) {
      if (active.has(key)) return null;
      const token = Symbol("keyed-operation");
      active.set(key, token);
      return token;
    },
    /**
     * @param {K} key
     * @param {symbol} token
     */
    isCurrent(key, token) {
      return active.get(key) === token;
    },
    /**
     * @param {K} key
     * @param {symbol} token
     */
    end(key, token) {
      if (active.get(key) !== token) return false;
      active.delete(key);
      return true;
    }
  };
}

/**
 * @template {{ id: number }} T
 * @param {T[]} items
 * @param {number} itemId
 * @returns {T[]}
 */
export function withoutItemId(items, itemId) {
  return items.filter((item) => item.id !== itemId);
}

/**
 * A lightweight summary is the cache-invalidation version for its full detail.
 * Invalid or equal timestamps are treated as non-authoritative.
 *
 * @param {{ id: number; updated_at: string }} detail
 * @param {{ id: number; updated_at: string } | undefined} summary
 */
export function summaryInvalidatesDetail(detail, summary) {
  if (!summary || detail.id !== summary.id) return false;
  const detailUpdatedAt = Date.parse(detail.updated_at);
  const summaryUpdatedAt = Date.parse(summary.updated_at);
  return (
    Number.isFinite(detailUpdatedAt)
    && Number.isFinite(summaryUpdatedAt)
    && summaryUpdatedAt > detailUpdatedAt
  );
}
