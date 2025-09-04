import { useState, useEffect } from "react";

const usePersistStore = <T, F>(
  store: (callback: (state: T) => unknown) => unknown,
  callback: (state: T) => F
) => {
  const result = store(callback) as F;
  const [data, setData] = useState<F>();
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    // Only update data after the component has hydrated
    setHasHydrated(true);
    setData(result);
  }, [result]);

  // Return undefined until hydration is complete to prevent mismatch
  if (!hasHydrated) {
    return undefined;
  }

  return data;
};

export default usePersistStore;
