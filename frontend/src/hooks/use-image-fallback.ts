import { useState, useEffect, useCallback } from "react";

export function useImageFallback(src: string) {
  const [error, setError] = useState(false);

  useEffect(() => {
    setError(false);
  }, [src]);

  const onError = useCallback(() => setError(true), []);

  return { error, onError } as const;
}
