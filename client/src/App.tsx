import { SidebarInset, SidebarProvider } from "./components/ui/sidebar"

import Campanha from "./components/campanha"
import Allowlist from "./components/allowlist"
import Achados from "./components/achados"
import Regras from "./components/regras"
import Auditoria from "./components/auditoria"
import NotFound from "./components/not-found"
import AppHeader from "./components/header"
import AppSidebar from "./components/sidebar"
import { useUrlStore } from "./stores/url.store"

const CAMPAIGN_ROUTES = ["", "#", "#campanha"]

function renderPage(currentUrl: string) {
  if (CAMPAIGN_ROUTES.includes(currentUrl)) return <Campanha />
  if (currentUrl === "#allowlist") return <Allowlist />
  if (currentUrl === "#achados") return <Achados />
  if (currentUrl === "#regras") return <Regras />
  if (currentUrl === "#auditoria") return <Auditoria />
  return <NotFound url={currentUrl} />
}

export function App() {
  const currentUrl = useUrlStore((state) => state.currentUrl)

  return (
    <div className="dark flex min-h-svh bg-background text-foreground">
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="min-w-0 px-4 sm:px-8">
          <AppHeader />
          {renderPage(currentUrl)}
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}

export default App
