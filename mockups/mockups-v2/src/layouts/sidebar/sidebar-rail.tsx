import { useTheme } from "@/themes/provider.tsx"
import { NavItem } from "./nav-item.tsx"
import { useNavItems, SidebarHeader, SidebarSearch } from "./shared.tsx"

/** Ice Station: Always-visible rail with icon + label */
export function SidebarRail() {
  const theme = useTheme()
  const navItems = useNavItems()

  return (
    <aside
      className="shrink-0 bg-bg-surface border-r border-border flex flex-col h-full overflow-hidden"
      style={{ width: theme.chrome.sidebarWidth }}
    >
      <SidebarHeader />
      <nav className="flex-1 overflow-y-auto py-2">
        {navItems.map((item) => (
          <NavItem key={item.label} {...item} />
        ))}
      </nav>
      <SidebarSearch />
    </aside>
  )
}
