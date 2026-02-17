import { useState, useEffect } from "react";
import { apiFetch } from "../api/client";

/**
 * Fetch pitch-type aggregation data for a pitcher and season.
 *
 * Calls the query_pitches API endpoint and returns the array of pitch type
 * aggregations (movement, velocity, spin, usage stats per pitch type).
 *
 * @param {number|string} pitcherId - MLBAM player ID.
 * @param {number} season - Season year (e.g. 2024).
 * @returns {{ pitches: Array|null, loading: boolean, error: string|null }}
 */
export default function usePitchData(pitcherId, season) {
  const [pitches, setPitches] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      setPitches(null);

      if (!pitcherId) {
        setLoading(false);
        return;
      }

      try {
        const data = await apiFetch(
          `/pitchers/${pitcherId}/pitches?season=${season}`,
        );

        if (!cancelled) {
          setPitches(data.pitches);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || "Failed to load pitch data");
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

  return { pitches, loading, error };
}
