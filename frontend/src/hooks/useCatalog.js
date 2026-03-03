import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../api/client";
import { readCache, writeCache } from "./catalogCache";
import { normalizeQuery } from "./normalizeQuery";

const MAX_RESULTS = 25;

/**
 * Fetch and cache a player catalog for a given role and season.
 *
 * Calls the catalog API which returns ``{ season, role, players }`` directly.
 * Caches the response in AsyncStorage for offline/fast reload. Exposes a
 * search function for last-name prefix matching.
 *
 * @param {string} role - "pitchers" or "batters"
 * @param {number} season - MLB season year (e.g. 2024)
 * @returns {{ catalog: object|null, loading: boolean, error: string|null, search: function }}
 */
export default function useCatalog(role, season) {
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        // Try cache first for instant display
        const cached = await readCache(role, season);
        if (cached && !cancelled) {
          setCatalog(cached.catalog);
        }

        // Always fetch fresh data from the API
        const data = await apiFetch(`/catalogs/${role}?season=${season}`);

        if (cancelled) return;

        await writeCache(role, season, data);
        setCatalog(data);
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load catalog");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [role, season]);

  const search = useCallback(
    (query) => {
      if (!catalog || !query) return [];
      const norm = normalizeQuery(query);
      if (!norm) return [];
      return catalog.players
        .filter((p) => p.last_norm.startsWith(norm))
        .slice(0, MAX_RESULTS);
    },
    [catalog],
  );

  return { catalog, loading, error, search };
}
