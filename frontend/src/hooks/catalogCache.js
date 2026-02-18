/**
 * localStorage helpers for caching catalog data by role and season.
 *
 * Key format: "doubleday:catalog:{role}:{season}"
 */

function cacheKey(role, season) {
  return `doubleday:catalog:${role}:${season}`;
}

/**
 * Read cached catalog and etag from localStorage.
 *
 * @param {string} role - Player role ("pitchers" or "batters").
 * @param {number} season - Season year.
 * @returns {{ catalog: object, etag: string } | null} Cached data or null if not cached.
 */
export function readCache(role, season) {
  try {
    const raw = localStorage.getItem(cacheKey(role, season));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed.etag || !parsed.catalog) return null;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Write catalog object and etag to localStorage.
 *
 * @param {string} role - Player role ("pitchers" or "batters").
 * @param {number} season - Season year.
 * @param {object} catalog - Parsed catalog.json object.
 * @param {string} etag - Etag from the manifest for cache invalidation.
 */
export function writeCache(role, season, catalog, etag) {
  localStorage.setItem(
    cacheKey(role, season),
    JSON.stringify({ catalog, etag }),
  );
}
