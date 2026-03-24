import { useTheme } from "@/themes/provider.tsx"
import { NavItem } from "./nav-item.tsx"
import { useNavItems, SidebarHeader, SidebarSearch } from "./shared.tsx"

/** Signal: Persistent sidebar with notification badges */
export function SidebarPersistent() {
  const theme = useTheme()
  const navItems = useNavItems()

  // Signal variation: show badges on more items from shared data
  const enhancedItems = navItems

  return (
    <aside
      className="shrink-0 bg-bg-surface border-r border-border flex flex-col h-full overflow-hidden"
      style={{ width: theme.chrome.sidebarWidth }}
    >
      <SidebarHeader />
      <nav className="flex-1 overflow-y-auto py-2">
        {enhancedItems.map((item) => (
          <NavItem key={item.label} {...item} />
        ))}
      </nav>
      <SidebarSearch />
    </aside>
  )
}
