import { Shield } from "lucide-react";
import { useSystemStatus } from "@/hooks/use-system-status";

/** Barra superior só para mobile (no desktop o sidebar já traz a marca). */
export function MobileTopbar() {
  const { data, isError } = useSystemStatus();
  const color = isError
    ? "bg-rose-500"
    : data?.status === "degraded"
      ? "bg-amber-400"
      : data
        ? "bg-emerald-400"
        : "bg-zinc-500";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/60 bg-background/80 px-4 backdrop-blur-xl lg:hidden">
      <a href="#" className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-xl border border-primary/30 bg-primary/10 text-primary">
          <Shield className="size-4" />
        </span>
        <span className="text-sm font-bold tracking-[0.18em]">
          PENT<span className="text-primary">.IA</span>
        </span>
      </a>
      <span
        className={`size-2.5 rounded-full ${color}`}
        title="Saúde da API"
        aria-label="Saúde da API"
      />
    </header>
  );
}
