import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../api/client";

/**
 * Fetch the current user's subscription status.
 *
 * Calls the subscription_status API endpoint and returns the subscription
 * state. Provides a refresh function for re-fetching after checkout.
 *
 * @returns {{ subscription: Object|null, loading: boolean, error: string|null, refresh: Function }}
 */
export default function useSubscription() {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch("/subscriptions/status");
      setSubscription(data);
    } catch (err) {
      setError(err.message || "Failed to load subscription status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return { subscription, loading, error, refresh: fetchStatus };
}
