import { useCallback, useEffect, useRef, useState } from 'react';

export function useResource<T>(loader: () => Promise<T>, interval = 0) {
  const loaderRef = useRef(loader);
  loaderRef.current = loader;
  const sequence = useRef(0);
  const mounted = useRef(false);
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    const current = ++sequence.current;
    try {
      const next = await loaderRef.current();
      if (mounted.current && current === sequence.current) { setData(next); setError(''); }
    } catch (cause) {
      if (mounted.current && current === sequence.current) setError(cause instanceof Error ? cause.message : 'ไม่สามารถโหลดข้อมูลได้');
    } finally {
      if (mounted.current && current === sequence.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const timer = interval ? window.setInterval(() => void refresh(), interval) : undefined;
    return () => { mounted.current = false; window.clearInterval(timer); };
  }, [interval, refresh]);
  return { data, error, loading, refresh };
}
