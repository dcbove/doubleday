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
 * Read cached catalog from AsyncStorage.
 *
 * @param {string} role - Player role ("pitchers" or "batters").
 * @param {number} season - Season year.
 * @returns {Promise<{ catalog: object } | null>} Cached data or null.
 */
export async function readCache(role, season) {
  try {
    const raw = await AsyncStorage.getItem(cacheKey(role, season));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed.catalog) return null;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Write catalog object to AsyncStorage.
 *
 * @param {string} role - Player role ("pitchers" or "batters").
 * @param {number} season - Season year.
 * @param {object} catalog - Parsed catalog response object.
 */
export async function writeCache(role, season, catalog) {
  await AsyncStorage.setItem(
    cacheKey(role, season),
    JSON.stringify({ catalog }),
  );
}
