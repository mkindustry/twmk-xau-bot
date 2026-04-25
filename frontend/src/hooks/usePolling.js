import { useState, useEffect, useCallback } from "react";

export function usePolling(fn, intervalMs = 5000) {
  const [data, setData]     = useState(null);
  const [error, setError]   = useState(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const result = await fn();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [fn]);

  useEffect(() => {
    fetch();
    const id = setInterval(fetch, intervalMs);
    return () => clearInterval(id);
  }, [fetch, intervalMs]);

  return { data, error, loading, refetch: fetch };
}
