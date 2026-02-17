import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../api/client";
import { readCache, writeCache } from "./catalogCache";
import { normalizeQuery } from "./normalizeQuery";

const MAX_RESULTS = 25;

/**
 * Fetch and cache a player catalog for a given role and season.
 *
 * Fetches the manifest via the authenticated API, checks localStorage for a
 * cached catalog matching the manifest's etag, and downloads the catalog blob
 * from CloudFront if the cache is stale or missing. Exposes a search function
 * for last-name prefix matching.
 *
 * @param {string} role - "pitchers" or "batters"
 * @param {number} season - MLB season year (e.g. 2024)
 * @returns {{ catalog: object|null, manifest: object|null, loading: boolean, error: string|null, search: function }}
 */
export default function useCatalog(role, season) {
  const [catalog, setCatalog] = useState(null);
  const [manifest, setManifest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      try {
        const data = await apiFetch(`/catalogs/${role}?season=${season}`);
        const manifestData = data.manifest;

        if (cancelled) return;
        setManifest(manifestData);

        const remoteEtag = manifestData.catalog.etag;

        const cached = readCache(role, season);
        if (cached && cached.etag === remoteEtag) {
          setCatalog(cached.catalog);
          setLoading(false);
          return;
        }

        const resp = await fetch(manifestData.catalog.url);
        if (!resp.ok) {
          throw new Error(`Catalog fetch failed: ${resp.status}`);
        }
        const catalogData = await resp.json();

        if (cancelled) return;

        writeCache(role, season, catalogData, remoteEtag);
        setCatalog(catalogData);
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

  return { catalog, manifest, loading, error, search };
}
