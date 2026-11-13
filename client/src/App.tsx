import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { LoaderCircle } from "lucide-react";
import { AmbientBackground } from "./components/layout/ambient-background";
import { MobileNav, Sidebar } from "./components/layout/sidebar";
import { MobileTopbar } from "./components/layout/topbar";
import { Login } from "./components/auth/login";
import { useAuth } from "./hooks/use-auth";
import { useHashRoute } from "./hooks/use-hash-route";
import { normalizeHash } from "./data/nav";
import { pageTransition } from "./lib/motion";

import Campanha from "./components/campanha";
import Achados from "./components/achados";
import Regras from "./components/regras";
import Allowlist from "./components/allowlist";
import Auditoria from "./components/auditoria";
import NotFound from "./components/not-found";

function renderPage(hash: string) {
  switch (normalizeHash(hash)) {
    case "#":
      return <Campanha />;
    case "#achados":
      return <Achados />;
    case "#regras":
      return <Regras />;
    case "#allowlist":
      return <Allowlist />;
    case "#auditoria":
      return <Auditoria />;
    default:
      return <NotFound url={hash} />;
  }
}

export function App() {
  const status = useAuth((s) => s.status);
  const bootstrap = useAuth((s) => s.bootstrap);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  if (status === "loading") {
    return (
      <div className="relative flex min-h-svh items-center justify-center text-muted-foreground">
        <AmbientBackground />
        <LoaderCircle className="size-6 animate-spin text-primary" />
      </div>
    );
  }

  if (status === "anon") {
    return <Login />;
  }

  return <Dashboard />;
}

function Dashboard() {
  const [hash, navigate] = useHashRoute();

  return (
    <div className="relative flex min-h-svh text-foreground">
      <AmbientBackground />
      <Sidebar current={hash} onNavigate={navigate} />

      <div className="flex min-w-0 flex-1 flex-col">
        <MobileTopbar />
        <main className="mx-auto w-full max-w-[1500px] flex-1 px-4 pb-24 pt-6 sm:px-6 lg:px-10 lg:pb-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={normalizeHash(hash)}
              variants={pageTransition}
              initial="hidden"
              animate="show"
              exit="exit"
            >
              {renderPage(hash)}
            </motion.div>
          </AnimatePresence>
        </main>
        <MobileNav current={hash} onNavigate={navigate} />
      </div>
    </div>
  );
}

export default App;
