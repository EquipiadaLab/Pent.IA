import { SidebarInset, SidebarProvider } from "./components/ui/sidebar"

import Campanha from "./components/campanha"
import AppHeader from "./components/header"
import AppSidebar from "./components/sidebar"

export function App() {
  return (
    <div className="flex min-h-svh">
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="px-8">
          <AppHeader />
          <Campanha />
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}

export default App
