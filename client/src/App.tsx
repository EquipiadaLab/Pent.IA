import { SidebarInset, SidebarProvider } from "./components/ui/sidebar"

import Campanha from "./components/campanha"
import Allowlist from "./components/allowlist"
import NotFound from "./components/not-found"
import AppHeader from "./components/header"
import AppSidebar from "./components/sidebar"
import { useUrlStore } from "./stores/url.store"

const CAMPAIGN_ROUTES = ["", "#", "#campanha"]

function renderPage(currentUrl: string) {
  if (CAMPAIGN_ROUTES.includes(currentUrl)) return <Campanha />
  if (currentUrl === "#allowlist") return <Allowlist />
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
