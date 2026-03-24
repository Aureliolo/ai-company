import type { ReactNode } from "react"
import { useTheme } from "@/themes/provider.tsx"
import { StatusBar } from "@/layouts/status-bar.tsx"
import { Sidebar } from "@/layouts/sidebar/sidebar.tsx"

interface AppShellProps {
  children: ReactNode
}

export function AppShell({ children }: AppShellProps) {
  const theme = useTheme()

  return (
    <div className="flex flex-col h-screen bg-bg-base overflow-hidden">
      {theme.chrome.statusBarVisible && <StatusBar />}
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 min-w-0 overflow-y-auto overflow-x-hidden bg-bg-base">
          {children}
        </main>
      </div>
    </div>
  )
}
