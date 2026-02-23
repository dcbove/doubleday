/**
 * Normalize a search query to match the last_norm field in catalog.json.
 *
 * Must mirror the Python normalize_name() in src/doubleday/util/mlb.py:
 * NFKD decomposition -> strip combining marks -> lowercase -> keep alphanumeric only.
 *
 * @param {string} query - Raw search query from the user.
 * @returns {string} Normalized string suitable for prefix matching.
 */
export function normalizeQuery(query) {
  return query
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}
