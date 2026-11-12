import { SidebarInset, SidebarProvider } from "./components/ui/sidebar"

import Campanha from "./components/campanha"
import AppHeader from "./components/header"
import AppSidebar from "./components/sidebar"

export function App() {
  return (
    <div className="dark flex min-h-svh bg-background text-foreground">
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="min-w-0 px-4 sm:px-8">
          <AppHeader />
          <Campanha />
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}

export default App
