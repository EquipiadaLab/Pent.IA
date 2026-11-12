import "./index.css"

import App from "./App.tsx"
import { SidebarProvider } from "./components/ui/sidebar.tsx"
import { StrictMode } from "react"
import { ThemeProvider } from "@/components/theme-provider.tsx"
import { createRoot } from "react-dom/client"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <SidebarProvider>
        <App />
      </SidebarProvider>
    </ThemeProvider>
  </StrictMode>
)
