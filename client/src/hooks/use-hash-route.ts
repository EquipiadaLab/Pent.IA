import { useCallback, useEffect, useState } from "react";
import { normalizeHash } from "@/data/nav";

/**
 * Roteamento por hash, sem dependências externas (nada de react-router).
 * Mantém o estado em sincronia com `window.location.hash` e expõe `navigate`.
 */
export function useHashRoute(): [string, (hash: string) => void] {
  const [hash, setHash] = useState(() => normalizeHash(window.location.hash));

  useEffect(() => {
    const onChange = () => setHash(normalizeHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((next: string) => {
    if (next === "#" || next === "") {
      // Volta à raiz sem deixar "#" pendurado na URL.
      history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
      setHash("#");
      return;
    }
    window.location.hash = next; // dispara hashchange → atualiza o estado
  }, []);

  return [hash, navigate];
}
