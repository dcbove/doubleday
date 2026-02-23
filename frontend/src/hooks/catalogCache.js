/**
 * AsyncStorage helpers for caching catalog data by role and season.
 *
 * Key format: "doubleday:catalog:{role}:{season}"
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

function cacheKey(role, season) {
  return `doubleday:catalog:${role}:${season}`;
}

/**
 * Read cached catalog and etag from AsyncStorage.
 *
 * @param {string} role - Player role ("pitchers" or "batters").
 * @param {number} season - Season year.
 * @returns {Promise<{ catalog: object, etag: string } | null>} Cached data or null.
 */
export async function readCache(role, season) {
  try {
    const raw = await AsyncStorage.getItem(cacheKey(role, season));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed.etag || !parsed.catalog) return null;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Write catalog object and etag to AsyncStorage.
 *
 * @param {string} role - Player role ("pitchers" or "batters").
 * @param {number} season - Season year.
 * @param {object} catalog - Parsed catalog.json object.
 * @param {string} etag - Etag from the manifest for cache invalidation.
 */
export async function writeCache(role, season, catalog, etag) {
  await AsyncStorage.setItem(
    cacheKey(role, season),
    JSON.stringify({ catalog, etag }),
  );
}
