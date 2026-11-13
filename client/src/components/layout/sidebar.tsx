import { motion } from "motion/react";
import { Activity, LogOut, Moon, Shield, ShieldCheck, Sun } from "lucide-react";
import { NAV_ITEMS, normalizeHash } from "@/data/nav";
import { useSystemStatus, type ComponentState } from "@/hooks/use-system-status";
import { useAuth } from "@/hooks/use-auth";
import { useTheme } from "@/components/theme-provider";
import { fadeUp, staggerContainer } from "@/lib/motion";

interface SidebarProps {
  current: string;
  onNavigate: (hash: string) => void;
}

const STATUS_COLOR: Record<ComponentState | "offline", string> = {
  ok: "bg-emerald-400",
  degraded: "bg-amber-400",
  error: "bg-rose-400",
  disabled: "bg-zinc-500",
  unchecked: "bg-zinc-500",
  offline: "bg-rose-500",
};

function Brand() {
  return (
    <a
      href="#"
      className="group flex items-center gap-3 rounded-2xl px-2 py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
    >
      <motion.span
        whileHover={{ rotate: -8, scale: 1.05 }}
        transition={{ type: "spring", stiffness: 300, damping: 15 }}
        className="grid size-10 place-items-center rounded-2xl border border-primary/30 bg-primary/10 text-primary shadow-[0_0_24px_-6px_var(--primary)]"
      >
        <Shield className="size-5" />
      </motion.span>
      <span className="flex flex-col leading-none">
        <span className="text-[15px] font-bold tracking-[0.18em] text-foreground">
          PENT<span className="text-primary">.IA</span>
        </span>
        <span className="mt-1 text-[8px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
          Pente fino no sistema
        </span>
      </span>
    </a>
  );
}

function NavButton({
  item,
  active,
  onClick,
}: {
  item: (typeof NAV_ITEMS)[number];
  active: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <motion.button
      type="button"
      variants={fadeUp}
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/50 ${
        active
          ? "text-foreground"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {active && (
        <motion.span
          layoutId="nav-active"
          className="absolute inset-0 -z-10 rounded-xl border border-primary/30 bg-primary/10"
          transition={{ type: "spring", stiffness: 380, damping: 32 }}
        />
      )}
      <Icon
        className={`size-[18px] shrink-0 transition-colors ${active ? "text-primary" : ""}`}
      />
      <span className="font-medium">{item.label}</span>
    </motion.button>
  );
}

function SystemHealth() {
  const { data, isError } = useSystemStatus();
  const state: ComponentState | "offline" = isError
    ? "offline"
    : (data?.status ?? "unchecked");
  const label = isError
    ? "Sem conexão"
    : data?.status === "degraded"
      ? "Com limitações"
      : data
        ? "Operacional"
        : "Verificando...";

  return (
    <div className="rounded-2xl border border-border/60 bg-card/40 p-3 backdrop-blur-sm">
      <div className="flex items-center gap-2.5">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-primary/20 bg-primary/10 text-primary">
          <Activity className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold text-foreground">Saúde da API</p>
          <div className="mt-1 flex items-center gap-1.5">
            <span className="relative flex size-2">
              <motion.span
                className={`absolute inline-flex size-full rounded-full ${STATUS_COLOR[state]} opacity-60`}
                animate={{ scale: [1, 1.9], opacity: [0.6, 0] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
              />
              <span
                className={`relative inline-flex size-2 rounded-full ${STATUS_COLOR[state]}`}
              />
            </span>
            <span className="truncate text-[11px] text-muted-foreground">
              {label}
            </span>
          </div>
        </div>
        {data?.planner && (
          <span className="shrink-0 rounded-md border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-muted-foreground">
            {data.planner === "ai" ? "IA" : "Regras"}
          </span>
        )}
      </div>
    </div>
  );
}

function UserFooter() {
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  if (!user) return null;
  const isAdmin = user.role === "admin";
  return (
    <div className="flex items-center gap-2.5 rounded-2xl border border-border/60 bg-card/40 p-2.5 backdrop-blur-sm">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-primary/20 bg-primary/10 text-[11px] font-bold uppercase text-primary">
        {user.username.slice(0, 2)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[12px] font-semibold text-foreground">
          {user.username}
        </p>
        <p className="flex items-center gap-1 text-[10px] text-muted-foreground">
          {isAdmin && <ShieldCheck className="size-3 text-primary" />}
          {isAdmin ? "Administrador" : "Operador"}
        </p>
      </div>
      <button
        type="button"
        onClick={logout}
        aria-label="Sair"
        title="Sair"
        className="grid size-8 shrink-0 place-items-center rounded-lg border border-border/60 text-muted-foreground outline-none transition-colors hover:border-rose-400/40 hover:text-rose-300 focus-visible:ring-2 focus-visible:ring-primary/50"
      >
        <LogOut className="size-4" />
      </button>
    </div>
  );
}

function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "dark" || theme === "system";
  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Ativar tema claro" : "Ativar tema escuro"}
      className="flex items-center justify-center gap-2 rounded-xl border border-border/60 bg-card/40 px-3 py-2 text-xs text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary/50"
    >
      {isDark ? <Moon className="size-3.5" /> : <Sun className="size-3.5" />}
      {isDark ? "Tema escuro" : "Tema claro"}
    </button>
  );
}

/** Rail de navegação — desktop (lg+). */
export function Sidebar({ current, onNavigate }: SidebarProps) {
  const active = normalizeHash(current);
  return (
    <aside className="sticky top-0 hidden h-svh w-[248px] shrink-0 flex-col gap-6 border-r border-border/50 bg-background/40 px-4 py-5 backdrop-blur-xl lg:flex">
      <Brand />
      <motion.nav
        variants={staggerContainer(0.05)}
        initial="hidden"
        animate="show"
        className="flex flex-1 flex-col gap-1"
      >
        {NAV_ITEMS.map((item) => (
          <NavButton
            key={item.hash}
            item={item}
            active={active === item.hash}
            onClick={() => onNavigate(item.hash)}
          />
        ))}
      </motion.nav>
      <div className="flex flex-col gap-2">
        <SystemHealth />
        <UserFooter />
        <ThemeToggle />
      </div>
    </aside>
  );
}

/** Barra inferior — mobile. */
export function MobileNav({ current, onNavigate }: SidebarProps) {
  const active = normalizeHash(current);
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex items-stretch justify-around border-t border-border/60 bg-background/80 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = active === item.hash;
        return (
          <button
            key={item.hash}
            type="button"
            onClick={() => onNavigate(item.hash)}
            aria-current={isActive ? "page" : undefined}
            className="relative flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] outline-none"
          >
            {isActive && (
              <motion.span
                layoutId="nav-active-mobile"
                className="absolute inset-x-2 top-0 h-0.5 rounded-full bg-primary"
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
              />
            )}
            <Icon
              className={`size-5 transition-colors ${isActive ? "text-primary" : "text-muted-foreground"}`}
            />
            <span
              className={isActive ? "text-foreground" : "text-muted-foreground"}
            >
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
