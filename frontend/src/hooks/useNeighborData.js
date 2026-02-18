import { useState, useEffect } from "react";
import { apiFetch } from "../api/client";

/**
 * Fetch shape-similarity neighbor data for a pitcher and season.
 *
 * Calls the query_neighbors API endpoint and returns the array of neighbor
 * pitchers ranked by similarity score.
 *
 * @param {number|string} pitcherId - MLBAM player ID.
 * @param {number} season - Season year (e.g. 2024).
 * @returns {{ neighbors: Array|null, loading: boolean, error: string|null }}
 */
export default function useNeighborData(pitcherId, season) {
  const [neighbors, setNeighbors] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      setNeighbors(null);

      if (!pitcherId) {
        setLoading(false);
        return;
      }

      try {
        const data = await apiFetch(
          `/pitchers/${pitcherId}/neighbors?season=${season}`,
        );

        if (!cancelled) {
          setNeighbors(data.neighbors);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load neighbor data");
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
  }, [pitcherId, season]);

  return { neighbors, loading, error };
}
