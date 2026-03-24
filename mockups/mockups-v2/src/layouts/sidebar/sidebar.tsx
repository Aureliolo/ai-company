import { useTheme } from "@/themes/provider.tsx"
import { SidebarRail } from "./sidebar-rail.tsx"
import { SidebarCollapsible } from "./sidebar-collapsible.tsx"
import { SidebarHidden } from "./sidebar-hidden.tsx"
import { SidebarPersistent } from "./sidebar-persistent.tsx"
import { SidebarCompact } from "./sidebar-compact.tsx"

export function Sidebar() {
  const theme = useTheme()

  switch (theme.chrome.sidebarMode) {
    case "rail":
      return <SidebarRail />
    case "collapsible":
      return <SidebarCollapsible />
    case "hidden":
      return <SidebarHidden />
    case "persistent":
      return <SidebarPersistent />
    case "compact":
      return <SidebarCompact />
  }
}
